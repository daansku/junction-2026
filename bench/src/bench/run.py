"""Score one model on the benchmark list with the fixed generation config.

Two ways to reach the model, same settings either way:
  --model <hf id | dir> [--lora <dir>]    load it in-process with vLLM (needs a free GPU)
  --api <base url ending in /v1> --served-name <name> --tokenizer <hf id | dir>
                                          an OpenAI-compatible vLLM server that already serves it (e.g. A3's
                                          `vllm serve` on the GPU box); key from $OPENAI_API_KEY

Passes:
  1. lm-evaluation-harness for the `lm_eval` benchmarks (generative tasks through chat completions with the chat
     template; multiple-choice tasks through loglikelihood)
  2. reasoning-gym items generated from a fixed seed, graded by reasoning-gym

Output directory (one per run):
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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import stats

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

# primary metric and preferred filter per lm-eval task family (first match wins)
METRIC_PREF = ["prompt_level_strict_acc", "exact_match", "math_verify", "acc_norm", "acc"]
FILTER_PREF = ["flexible-extract", "custom-extract", "get_response", "none", "strict-match"]
MC_TASKS = {"medqa_4options"}          # loglikelihood multiple choice (checked in lm-eval 0.4.13)


def load_configs(benchmarks: str | None = None, generation: str | None = None) -> tuple[dict, dict]:
    b = yaml.safe_load(Path(benchmarks or CONFIG_DIR / "benchmarks.yaml").read_text(encoding="utf-8"))
    g = yaml.safe_load(Path(generation or CONFIG_DIR / "generation.yaml").read_text(encoding="utf-8"))
    return b, g


def select(bcfg: dict, only: list[str] | None, dev_slice: bool) -> list[dict]:
    out = []
    for tier, t in bcfg["tiers"].items():
        for bm in t.get("benchmarks") or []:
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
def _gen_kwargs(g: dict) -> dict:
    s = g["sampling"]
    return {"do_sample": True, **{k: s[k] for k in ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty")},
            "max_gen_toks": g["max_gen_toks"]}


def _model_spec(a, g: dict, mc: bool) -> tuple[str, dict]:
    """lm-eval --model and --model_args for in-process vLLM or an OpenAI-compatible server."""
    if a.api:
        base = a.api.rstrip("/")
        if mc:  # loglikelihood needs the completions endpoint and a local tokenizer
            return "local-completions", {"model": a.served_name, "base_url": f"{base}/completions",
                                         "tokenizer": a.tokenizer, "tokenizer_backend": "huggingface",
                                         "num_concurrent": a.concurrency, "max_retries": 5, "timeout": 600}
        return "local-chat-completions", {"model": a.served_name, "base_url": f"{base}/chat/completions",
                                          "num_concurrent": a.concurrency, "max_retries": 5, "timeout": 1800,
                                          "tokenized_requests": False, "think_end_token": g["think_end_token"]}
    margs = {"pretrained": a.model, "dtype": g["vllm"]["dtype"], "gpu_memory_utilization": g["vllm"]["gpu_memory_utilization"],
             "max_model_len": g["max_model_len"], "seed": g["seed"], "think_end_token": g["think_end_token"],
             "language_model_only": g["vllm"]["language_model_only"]}
    if a.lora:
        margs.update({"lora_local_path": a.lora, "max_lora_rank": 64, "enable_lora": True})
    return "vllm", margs


def run_lm_eval(a, benches: list[dict], g: dict, out: Path) -> list[dict]:
    lm = [b for b in benches if b["kind"] == "lm_eval"]
    if not lm:
        return []
    raw = out / "lm_eval"
    raw.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    # one lm-eval invocation per (limit, fewshot, mc) group: --limit and --num_fewshot are global flags
    groups: dict = {}
    for b in lm:
        groups.setdefault((b.get("limit"), b.get("fewshot"), b["task"] in MC_TASKS), []).append(b)
    env = {**os.environ, "HF_DATASETS_TRUST_REMOTE_CODE": "1"}
    for (limit, fewshot, mc), group in groups.items():
        model, margs = _model_spec(a, g, mc)
        cmd = [a.python or sys.executable, "-m", "lm_eval", "--model", model,
               "--model_args", ",".join(f"{k}={v}" for k, v in margs.items()),
               "--tasks", ",".join(b["task"] for b in group),
               "--log_samples", "--output_path", str(raw), "--seed", str(g["seed"])]
        if not mc:
            # chat template + few-shot examples as earlier turns; sampling settings from generation.yaml
            cmd += ["--apply_chat_template", "--fewshot_as_multiturn",
                    "--gen_kwargs", ",".join(f"{k}={v}" for k, v in _gen_kwargs(g).items())]
        if not a.api:
            # lm-eval defaults to batch_size 1, which hands vLLM one request at a time; "auto" lets vLLM batch
            cmd += ["--batch_size", "auto"]
        if limit:
            cmd += ["--limit", str(limit)]
        if fewshot is not None:
            cmd += ["--num_fewshot", str(fewshot)]
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True, env=env)
        for b in group:
            items += parse_lm_eval_samples(raw, b)
        _save(out, items_so_far=items, tag=f"lm_eval group {group[0]['id']}")
    return items


def parse_lm_eval_samples(raw: Path, b: dict) -> list[dict]:
    task = b["task"]
    files = [f for f in glob.glob(str(raw / "**" / "samples_*.jsonl"), recursive=True)
             if Path(f).name.startswith(f"samples_{task}_")]
    if not files:
        raise RuntimeError(f"no lm-eval samples for {task} under {raw}")
    newest: dict[str, str] = {}
    for f in sorted(files, key=os.path.getmtime):     # last write per subtask wins (reruns)
        sub = Path(f).name[len("samples_"):].rsplit("_", 1)[0]
        newest[sub] = f
    best: dict = {}
    for sub, f in newest.items():
        if sub != task and not sub.startswith(task + "_"):
            continue
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            metric = next((m for m in METRIC_PREF if m in r), None)
            if metric is None:
                continue
            filt = r.get("filter", "none")
            key = f"{sub}:{r['doc_id']}"
            rank = FILTER_PREF.index(filt) if filt in FILTER_PREF else len(FILTER_PREF)
            if key not in best or rank < best[key][0]:
                best[key] = (rank, {"bench": b["id"], "item": key, "subtask": sub, "score": float(r[metric]),
                                    "metric": metric, "filter": filt})
    return [v[1] for v in best.values()]


# ---------------------------------------------------------------- reasoning-gym pass
def _rg_generate_inprocess(a, g: dict, convs: list[list[dict]]) -> list[tuple[str, bool, int]]:
    from vllm import LLM, SamplingParams
    s = g["sampling"]
    llm_kw = dict(model=a.model, dtype=g["vllm"]["dtype"], gpu_memory_utilization=g["vllm"]["gpu_memory_utilization"],
                  max_model_len=g["max_model_len"], seed=g["seed"], language_model_only=g["vllm"]["language_model_only"])
    if a.lora:
        llm_kw.update(enable_lora=True, max_lora_rank=64)
    llm = LLM(**llm_kw)
    sp = SamplingParams(temperature=s["temperature"], top_p=s["top_p"], top_k=s["top_k"], min_p=s["min_p"],
                        presence_penalty=s["presence_penalty"], repetition_penalty=s["repetition_penalty"],
                        max_tokens=g["max_gen_toks"], seed=g["seed"])
    lora_req = None
    if a.lora:
        from vllm.lora.request import LoRARequest
        lora_req = LoRARequest("cand", 1, a.lora)
    outs = llm.chat(convs, sp, lora_request=lora_req, use_tqdm=True,
                    chat_template_kwargs={"enable_thinking": bool(g.get("thinking", True))})
    res = [(o.outputs[0].text, o.outputs[0].finish_reason == "length", len(o.outputs[0].token_ids)) for o in outs]
    del llm
    return res


def _rg_generate_api(a, g: dict, convs: list[list[dict]]) -> list[tuple[str, bool, int]]:
    import httpx
    s = g["sampling"]
    url = a.api.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', 'EMPTY')}"}

    def one(i_conv):
        i, conv = i_conv
        body = {"model": a.served_name, "messages": conv, "max_tokens": g["max_gen_toks"], "seed": g["seed"] + i,
                **{k: s[k] for k in ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty")}}
        for attempt in range(5):
            try:
                r = httpx.post(url, json=body, headers=headers, timeout=1800)
                r.raise_for_status()
                c = r.json()["choices"][0]
                msg = c["message"]
                # a server with a reasoning parser puts thinking in reasoning_content; re-join so grading is uniform
                text = (f"{msg.get('reasoning_content')}{g['think_end_token']}" if msg.get("reasoning_content") else "") + (msg.get("content") or "")
                return text, c.get("finish_reason") == "length", int((r.json().get("usage") or {}).get("completion_tokens") or 0)
            except Exception as e:  # noqa: BLE001
                if attempt == 4:
                    print(f"reasoning-gym item {i} failed: {e}", flush=True)
                    return "", False, 0
                time.sleep(2 * (attempt + 1))

    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        return list(ex.map(one, enumerate(convs)))


def run_reasoning_gym(a, benches: list[dict], g: dict, out: Path) -> list[dict]:
    rgb = [b for b in benches if b["kind"] == "reasoning_gym"]
    if not rgb:
        return []
    import reasoning_gym as rg
    from reasoning_gym.utils import SYSTEM_PROMPTS, extract_answer

    raw = out / "reasoning_gym"
    raw.mkdir(parents=True, exist_ok=True)
    sysmsg = SYSTEM_PROMPTS[g.get("reasoning_gym_system_prompt", "default")]
    jobs = []
    for b in rgb:
        ds = rg.create_dataset(b["dataset"], size=b["n"], seed=g["dataset_seed"])
        for i, entry in enumerate(ds):
            jobs.append((b, i, ds, entry, [{"role": "system", "content": sysmsg}, {"role": "user", "content": entry["question"]}]))
    t0 = time.time()
    gen = (_rg_generate_api if a.api else _rg_generate_inprocess)(a, g, [j[4] for j in jobs])
    print(f"reasoning-gym: {len(jobs)} items in {time.time() - t0:.0f}s", flush=True)
    items, dumps = [], {}
    end = g["think_end_token"]
    for (b, i, ds, entry, _), (text, truncated, ntok) in zip(jobs, gen):
        answer_part = text.split(end, 1)[1] if end in text else ("" if g.get("thinking", True) else text)
        ans = extract_answer(answer_part)
        try:
            score = float(ds.score_answer(answer=ans, entry=entry))
        except Exception:  # a malformed answer scores 0, never crashes the run
            score = 0.0
        items.append({"bench": b["id"], "item": f"{b['dataset']}:{g['dataset_seed']}:{i}", "score": score,
                      "truncated": truncated, "gen_tokens": ntok})
        dumps.setdefault(b["id"], []).append({"i": i, "answer": ans, "expected": entry.get("answer"), "score": score,
                                              "truncated": truncated, "response_tail": text[-1500:]})
    for k, v in dumps.items():
        (raw / f"{k}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in v), encoding="utf-8")
    return items


# ---------------------------------------------------------------- summary
def summarize(items: list[dict], benches: list[dict], bcfg: dict, meta: dict) -> dict:
    per: dict[str, dict[str, float]] = {}
    trunc: dict[str, int] = {}
    for it in items:
        per.setdefault(it["bench"], {})[it["item"]] = it["score"]
        trunc[it["bench"]] = trunc.get(it["bench"], 0) + int(bool(it.get("truncated")))
    tiers: dict[str, list[str]] = {}
    for b in benches:
        tiers.setdefault(b["tier"], []).append(b["id"])
    out = {**meta,
           "benchmarks": {b["id"]: {"tier": b["tier"], **stats.mean_ci(list(per.get(b["id"], {}).values())),
                                    "truncated": trunc.get(b["id"], 0)} for b in benches},
           "tiers": {t: stats.tier_mean(per, ids) for t, ids in tiers.items()}}
    # derived subsets (e.g. the pre-declared BBH subset), computed from an existing benchmark's items
    for tier, t in bcfg["tiers"].items():
        if "from" in t and t["from"] in per:
            sub = {}
            for name in t["subtasks"]:
                vals = [it["score"] for it in items if it["bench"] == t["from"] and name in it.get("subtask", "")]
                sub[name] = stats.mean_ci(vals)
            out.setdefault("subsets", {})[tier] = sub
    return out


def _save(out: Path, items_so_far: list[dict], tag: str) -> None:
    (out / "items.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items_so_far), encoding="utf-8")
    print(f"saved {len(items_so_far)} items ({tag})", flush=True)


def main_run(a) -> int:
    # vLLM's FlashInfer top-k/top-p sampler JIT-compiles with ninja/nvcc, which the box lacks; the
    # PyTorch sampler gives the same distribution. Put the venv's bin (ninja) on PATH for other JIT kernels.
    os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    if a.api and not (a.served_name and a.tokenizer):
        print("--api needs --served-name and --tokenizer", file=sys.stderr)
        return 2
    if not a.api and not a.model:
        print("give --model (in-process) or --api (server)", file=sys.stderr)
        return 2
    bcfg, g = load_configs(a.benchmarks, a.generation)
    benches = select(bcfg, a.only.split(",") if a.only else None, a.dev_slice)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {"name": a.name or out.name, "model": a.model or a.served_name, "api": a.api, "tokenizer": a.tokenizer,
            "lora": a.lora, "dev_slice": a.dev_slice, "benchmarks_version": bcfg["version"],
            "generation_version": g["version"], "config_hash": _config_hash(bcfg, g, a.dev_slice), "generation": g,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    t0 = time.time()
    items: list[dict] = []
    items_path = out / "items.jsonl"
    if a.resume and items_path.exists():
        items = [json.loads(l) for l in items_path.open(encoding="utf-8")]
        done = {i["bench"] for i in items}
        todo = [b for b in benches if b["id"] not in done]
    else:
        todo = benches
    if not a.skip_lm_eval:
        items += run_lm_eval(a, todo, g, out)
        _save(out, items, "lm_eval done")
    if not a.skip_rg:
        items += run_reasoning_gym(a, todo, g, out)
        _save(out, items, "reasoning_gym done")
    meta["wall_s"] = round(time.time() - t0)
    summary = summarize(items, benches, bcfg, meta)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for bid, r in summary["benchmarks"].items():
        m = r["mean"]
        ci = "" if m is None else f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
        print(f"{bid:22s} {r['tier']:24s} n={r['n']:5d} mean={'-' if m is None else f'{m:.3f}'} {ci} trunc={r['truncated']}")
    for t, r in summary["tiers"].items():
        print(f"tier {t:24s} mean={r['mean']}")
    return 0
