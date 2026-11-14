"""bench CLI.

  python -m bench run --model <hf id | local dir> [--lora <adapter dir>] --out data/derived/bench/<run> [--dev-slice]
  python -m bench run --api http://127.0.0.1:8001/v1 --served-name arena-base --tokenizer Qwen/Qwen3.5-9B --out ...
  python -m bench compare --ref data/derived/bench/base --cand data/derived/bench/sft-mix [--out delta.json]
  python -m bench list          # print the frozen benchmark list

`run` needs the GPU extras (vLLM, lm-eval, reasoning-gym); `compare` and `list` run anywhere.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _items(run_dir: str) -> dict[str, dict[str, float]]:
    per: dict[str, dict[str, float]] = {}
    for line in (Path(run_dir) / "items.jsonl").open(encoding="utf-8"):
        it = json.loads(line)
        per.setdefault(it["bench"], {})[it["item"]] = float(it["score"])
    return per


def cmd_compare(a) -> int:
    from . import stats
    ref, cand = _items(a.ref), _items(a.cand)
    sref = json.loads((Path(a.ref) / "summary.json").read_text(encoding="utf-8"))
    scand = json.loads((Path(a.cand) / "summary.json").read_text(encoding="utf-8"))
    if sref.get("config_hash") != scand.get("config_hash"):
        print(f"WARNING: config_hash differs ({sref.get('config_hash')} vs {scand.get('config_hash')}): "
              "runs used different benchmark lists or generation settings; deltas are not valid", file=sys.stderr)
    tiers = {k: v["tier"] for k, v in sref["benchmarks"].items()}
    out = {"ref": sref.get("name"), "cand": scand.get("name"), "config_hash_match": sref.get("config_hash") == scand.get("config_hash"),
           "benchmarks": {}, "tiers": {}}
    for b in sorted(set(ref) | set(cand)):
        out["benchmarks"][b] = {"tier": tiers.get(b), **stats.paired_delta(ref.get(b, {}), cand.get(b, {}))}
    # tier delta: paired bootstrap over items pooled per benchmark would weight big benchmarks; use the
    # unweighted mean of per-benchmark deltas (each benchmark counts once), as the protocol states
    for t in sorted({v for v in tiers.values() if v}):
        ds = [r["delta"] for r in out["benchmarks"].values() if r["tier"] == t and r["delta"] is not None]
        out["tiers"][t] = {"benchmarks": len(ds), "mean_delta": sum(ds) / len(ds) if ds else None}
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    for b, r in out["benchmarks"].items():
        if r["delta"] is None:
            print(f"{b:28s} no shared items")
            continue
        flag = "*" if r["excludes_zero"] else " "
        print(f"{b:28s} {r['mean_a']:.3f} -> {r['mean_b']:.3f}  delta {r['delta']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}]{flag} n={r['n_shared']}")
    for t, r in out["tiers"].items():
        print(f"tier {t:23s} mean delta {r['mean_delta']:+.3f} over {r['benchmarks']} benchmarks" if r["mean_delta"] is not None else f"tier {t}: -")
    return 0


def cmd_list(a) -> int:
    from .run import load_configs
    b, g = load_configs()
    for tier, t in b["tiers"].items():
        print(f"[{tier}]")
        if "from" in t:
            print(f"  (subset of {t['from']}: {', '.join(t['subtasks'])})")
        for bm in t.get("benchmarks") or []:
            print(f"  {bm['id']:28s} {bm['kind']:14s} {bm.get('task') or bm.get('dataset')}"
                  f"{'  fewshot ' + str(bm['fewshot']) if bm.get('fewshot') is not None else ''}"
                  f"{'  limit ' + str(bm['limit']) if bm.get('limit') else ''}{'  n ' + str(bm['n']) if bm.get('n') else ''}")
    print("dev slice:", ", ".join(b["dev_slice"]), f"(<= {b['dev_slice_limit']} items each)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bench")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="score one model (GPU)")
    r.add_argument("--model", help="HF id or local dir of the (merged) model, loaded in-process with vLLM")
    r.add_argument("--api", help="OpenAI-compatible base URL ending in /v1 of a vLLM server already serving the model")
    r.add_argument("--served-name", help="model name on that server (with --api)")
    r.add_argument("--tokenizer", help="HF id or dir of the tokenizer (with --api; loglikelihood tasks need it)")
    r.add_argument("--concurrency", type=int, default=48, help="parallel requests to the server (with --api)")
    r.add_argument("--gpu-mem", type=float, help="in-process vLLM memory share, overrides generation.yaml (results unchanged)")
    r.add_argument("--lora", help="LoRA adapter dir on top of --model")
    r.add_argument("--out", required=True)
    r.add_argument("--name")
    r.add_argument("--dev-slice", action="store_true", help="the small RL-checkpoint slice only")
    r.add_argument("--only", help="comma-separated benchmark ids")
    r.add_argument("--resume", action="store_true", help="skip benchmarks already in items.jsonl")
    r.add_argument("--skip-lm-eval", action="store_true")
    r.add_argument("--skip-rg", action="store_true")
    r.add_argument("--benchmarks")
    r.add_argument("--generation")
    r.add_argument("--python", help="python with lm-eval installed (default: this one)")
    c = sub.add_parser("compare", help="paired deltas between two runs")
    c.add_argument("--ref", required=True)
    c.add_argument("--cand", required=True)
    c.add_argument("--out")
    sub.add_parser("list", help="print the benchmark list")
    rs = sub.add_parser("rescore", help="re-parse a finished run's raw lm-eval samples (no generation)")
    rs.add_argument("--out", required=True)
    rs.add_argument("--benchmarks")
    rs.add_argument("--generation")
    a = p.parse_args(argv)
    if a.cmd == "run":
        from .run import main_run
        return main_run(a)
    if a.cmd == "rescore":
        from .run import main_rescore
        return main_rescore(a)
    return {"compare": cmd_compare, "list": cmd_list}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
