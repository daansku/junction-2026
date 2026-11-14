"""Score one model on the benchmark list with the fixed generation config.

GPU side (the Verda box). Two passes, each loading the model once:
  1. lm-evaluation-harness (vLLM backend, chat template) for the `lm_eval` benchmarks
  2. reasoning-gym items generated from a fixed seed, generated with vLLM, graded by reasoning-gym

Output directory layout (one directory per run):
  items.jsonl    one line per graded item: {"bench", "item", "score", ...}   <- paired comparisons use this
  summary.json   per-benchmark mean + 95% bootstrap CI, tier means, model, configs, timings
  lm_eval/       raw lm-eval output (results + samples), kept for audit
  reasoning_gym/ raw generations per dataset, kept for audit
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

from . import stats

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

# primary metric and preferred filter per lm-eval task family (first match wins)
METRIC_PREF = ["prompt_level_strict_acc", "exact_match", "math_verify", "acc_norm", "acc"]
FILTER_PREF = ["flexible-extract", "custom-extract", "get_response", "none", "strict-match"]


def load_configs(benchmarks: str | None = None, generation: str | None = None) -> tuple[dict, dict]:
    b = yaml.safe_load(Path(benchmarks or CONFIG_DIR / "benchmarks.yaml").read_text(encoding="utf-8"))
    g = yaml.safe_load(Path(generation or CONFIG_DIR / "generation.yaml").read_text(encoding="utf-8"))
    return b, g


def select(bcfg: dict, only: list[str] | None, dev_slice: bool) -> list[dict]:
    out = []
    for tier, t in bcfg["tiers"].items():
        for bm in t["benchmarks"]:
            if dev_slice and bm["id"] not in bcfg["dev_slice"]:
                continue
            if only and bm["id"] not in only:
                continue
            out.append({**bm, "tier": tier})
    if dev_slice:
        lim = bcfg.get("dev_slice_limit")
        for bm in out:
            if bm["kind"] == "reasoning_gym":
                bm["n"] = min(bm["n"], lim)
            else:
                bm["limit"] = min(bm.get("limit") or lim, lim)
    return out


def _config_hash(*objs) -> str:
    return hashlib.sha256(json.dumps(objs, sort_keys=True).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- lm-eval pass
def run_lm_eval(model: str, lora: str | None, benches: list[dict], g: dict, out: Path, python: str) -> list[dict]:
    lm = [b for b in benches if b["kind"] == "lm_eval"]
    if not lm:
        return []
    raw = out / "lm_eval"
    raw.mkdir(parents=True, exist_ok=True)
    s = g["sampling"]
    margs = {"pretrained": model, "dtype": g["vllm"]["dtype"], "gpu_memory_utilization": g["vllm"]["gpu_memory_utilization"],
             "max_model_len": g["max_model_len"], "seed": g["seed"], "think_end_token": g["think_end_token"],
             "language_model_only": g["vllm"]["language_model_only"]}
    if lora:
        margs.update({"lora_local_path": lora, "max_lora_rank": 64, "enable_lora": True})
    gen = {"do_sample": True, **{k: s[k] for k in ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty")},
           "max_gen_toks": g["max_gen_toks"]}
    items: list[dict] = []
    # tasks with a limit run in their own invocation (lm-eval's --limit is global)
    groups: dict = {}
    for b in lm:
        groups.setdefault(b.get("limit"), []).append(b)
    for limit, group in groups.items():
        cmd = [python, "-m", "lm_eval", "--model", "vllm",
               "--model_args", ",".join(f"{k}={v}" for k, v in margs.items()),
               "--tasks", ",".join(b["task"] for b in group), "--apply_chat_template",
               "--gen_kwargs", ",".join(f"{k}={v}" for k, v in gen.items()),
               "--log_samples", "--output_path", str(raw), "--seed", str(g["seed"]),
               # lm-eval defaults to batch_size 1, which hands vLLM one request at a time (~25 s/item here);
               # "auto" passes the whole task so vLLM batches it. Results are unchanged (per-request seeds).
               "--batch_size", "auto"]
        if limit:
            cmd += ["--limit", str(limit)]
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True, env={**os.environ, "HF_DATASETS_TRUST_REMOTE_CODE": "1"})
        for b in group:
            items += parse_lm_eval_samples(raw, b)
    return items


def _task_prefixes(task: str) -> list[str]:
    # group tasks (leaderboard_musr, mmlu_pro) write one samples file per subtask
    return [task + "_", task]


def parse_lm_eval_samples(raw: Path, b: dict) -> list[dict]:
    files = [f for f in glob.glob(str(raw / "**" / "samples_*.jsonl"), recursive=True)
             if any(Path(f).name.startswith("samples_" + p) for p in _task_prefixes(b["task"]))]
    if not files:
        raise RuntimeError(f"no lm-eval samples for {b['task']} under {raw}")
    newest: dict[str, str] = {}
    for f in sorted(files, key=os.path.getmtime):     # last write per subtask wins (reruns)
        sub = Path(f).name.rsplit("_", 1)[0]
        newest[sub] = f
    best: dict = {}
    for sub, f in newest.items():
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            metric = next((m for m in METRIC_PREF if m in r), None)
            if metric is None:
                continue
            filt = r.get("filter", "none")
            key = f"{sub}:{r['doc_id']}"
            rank = FILTER_PREF.index(filt) if filt in FILTER_PREF else len(FILTER_PREF)
            if key not in best or rank < best[key][0]:
                truncated = False
                resps = r.get("filtered_resps") or r.get("resps")
                best[key] = (rank, {"bench": b["id"], "item": key, "score": float(r[metric]), "metric": metric,
                                    "filter": filt, "truncated": truncated})
    return [v[1] for v in best.values()]


# ---------------------------------------------------------------- reasoning-gym pass
def run_reasoning_gym(model: str, lora: str | None, benches: list[dict], g: dict, out: Path) -> list[dict]:
    rgb = [b for b in benches if b["kind"] == "reasoning_gym"]
    if not rgb:
        return []
    import reasoning_gym as rg
    from reasoning_gym.utils import SYSTEM_PROMPTS, extract_answer
    from vllm import LLM, SamplingParams

    raw = out / "reasoning_gym"
    raw.mkdir(parents=True, exist_ok=True)
    s = g["sampling"]
    llm_kw = dict(model=model, dtype=g["vllm"]["dtype"], gpu_memory_utilization=g["vllm"]["gpu_memory_utilization"],
                  max_model_len=g["max_model_len"], seed=g["seed"], language_model_only=g["vllm"]["language_model_only"])
    if lora:
        llm_kw.update(enable_lora=True, max_lora_rank=64)
    llm = LLM(**llm_kw)
    sp = SamplingParams(temperature=s["temperature"], top_p=s["top_p"], top_k=s["top_k"], min_p=s["min_p"],
                        presence_penalty=s["presence_penalty"], repetition_penalty=s["repetition_penalty"],
                        max_tokens=g["max_gen_toks"], seed=g["seed"])
    lora_req = None
    if lora:
        from vllm.lora.request import LoRARequest
        lora_req = LoRARequest("cand", 1, lora)
    sysmsg = SYSTEM_PROMPTS[g.get("reasoning_gym_system_prompt", "default")]

    jobs = []
    for b in rgb:
        ds = rg.create_dataset(b["dataset"], size=b["n"], seed=g["dataset_seed"])
        for i, entry in enumerate(ds):
            jobs.append((b, i, ds, entry, [{"role": "system", "content": sysmsg},
                                           {"role": "user", "content": entry["question"]}]))
    t0 = time.time()
    outs = llm.chat([j[4] for j in jobs], sp, lora_request=lora_req, use_tqdm=True,
                    chat_template_kwargs={"enable_thinking": bool(g.get("thinking", True))})
    print(f"reasoning-gym: {len(jobs)} items in {time.time() - t0:.0f}s", flush=True)
    items, dumps = [], {}
    end = g["think_end_token"]
    for (b, i, ds, entry, _), o in zip(jobs, outs):
        text = o.outputs[0].text
        truncated = o.outputs[0].finish_reason == "length"
        answer_part = text.split(end, 1)[1] if end in text else ("" if g.get("thinking", True) else text)
        ans = extract_answer(answer_part)
        try:
            score = float(ds.score_answer(answer=ans, entry=entry))
        except Exception:  # a malformed answer scores 0, never crashes the run
            score = 0.0
        items.append({"bench": b["id"], "item": f"{b['dataset']}:{g['dataset_seed']}:{i}", "score": score,
                      "truncated": truncated, "gen_tokens": len(o.outputs[0].token_ids)})
        dumps.setdefault(b["id"], []).append({"i": i, "answer": ans, "expected": entry.get("answer"), "score": score,
                                              "truncated": truncated, "response_tail": text[-1500:]})
    for k, v in dumps.items():
        (raw / f"{k}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in v), encoding="utf-8")
    del llm
    return items


# ---------------------------------------------------------------- summary
def summarize(items: list[dict], benches: list[dict], meta: dict) -> dict:
    per: dict[str, dict[str, float]] = {}
    trunc: dict[str, int] = {}
    for it in items:
        per.setdefault(it["bench"], {})[it["item"]] = it["score"]
        trunc[it["bench"]] = trunc.get(it["bench"], 0) + int(bool(it.get("truncated")))
    tiers: dict[str, list[str]] = {}
    for b in benches:
        tiers.setdefault(b["tier"], []).append(b["id"])
    return {**meta,
            "benchmarks": {b["id"]: {"tier": b["tier"], **stats.mean_ci(list(per.get(b["id"], {}).values())),
                                     "truncated": trunc.get(b["id"], 0)} for b in benches},
            "tiers": {t: stats.tier_mean(per, ids) for t, ids in tiers.items()}}


def main_run(a) -> int:
    # vLLM's FlashInfer top-k/top-p sampler JIT-compiles with ninja/nvcc, which the box lacks; the
    # PyTorch sampler gives the same distribution. Put the venv's bin (ninja) on PATH for other JIT kernels.
    os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    bcfg, g = load_configs(a.benchmarks, a.generation)
    benches = select(bcfg, a.only.split(",") if a.only else None, a.dev_slice)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {"name": a.name or out.name, "model": a.model, "lora": a.lora, "dev_slice": a.dev_slice,
            "benchmarks_version": bcfg["version"], "generation_version": g["version"],
            "config_hash": _config_hash(bcfg, g), "generation": g, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    t0 = time.time()
    items: list[dict] = []
    items_path = out / "items.jsonl"
    if a.resume and items_path.exists():
        items = [json.loads(l) for l in items_path.open(encoding="utf-8")]
        done = {i["bench"] for i in items}
        benches_todo = [b for b in benches if b["id"] not in done]
    else:
        benches_todo = benches
    if not a.skip_lm_eval:
        items += run_lm_eval(a.model, a.lora, benches_todo, g, out, a.python or sys.executable)
        items_path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")
    if not a.skip_rg:
        items += run_reasoning_gym(a.model, a.lora, benches_todo, g, out)
        items_path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")
    meta["wall_s"] = round(time.time() - t0)
    summary = summarize(items, benches, meta)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for bid, r in summary["benchmarks"].items():
        m = r["mean"]
        print(f"{bid:28s} n={r['n']:5d} mean={'-' if m is None else f'{m:.3f}'} "
              f"[{'' if m is None else f'{r['ci_low']:.3f}, {r['ci_high']:.3f}'}] trunc={r['truncated']}")
    return 0
