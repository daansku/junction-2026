"""Run every policy on a fixed set of seeds and report scores.

    python -m switchboard.eval                       # all tiers, scripted policies
    python -m switchboard.eval --tiers hard --seeds 0-9
    python -m switchboard.eval --llm openai:gpt-5 --runs 3   # adds an LLM agent (see llm_agent.py)
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from .env import SwitchboardEnv
from .solvers import POLICIES


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines); never overrides variables already set."""
    import os
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def parse_seeds(s: str) -> list[int]:
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += range(int(a), int(b) + 1)
        else:
            out.append(int(part))
    return out


def run_policy(name, fn, tier, seeds, run_idx=0):
    rows = []
    for seed in seeds:
        env = SwitchboardEnv(seed, tier)
        t0 = time.time()
        fn(env, rng_seed=seed * 1000 + run_idx)
        row = env.summary()
        row.update(policy=name, run=run_idx, seconds=round(time.time() - t0, 2))
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="easy,medium,hard")
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--policies", default="oracle,rules_blind,noop,stop_early,random,greedy")
    ap.add_argument("--llm", action="append", default=[], help="provider:model, e.g. openai:gpt-5 (repeatable)")
    ap.add_argument("--runs", type=int, default=3, help="repeated runs for LLM agents")
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)
    load_dotenv()

    seeds = parse_seeds(args.seeds)
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    all_rows = []
    for tier in args.tiers.split(","):
        for p in args.policies.split(","):
            all_rows += run_policy(p, POLICIES[p], tier, seeds)
        for spec in args.llm:
            from .llm_agent import make_llm_policy
            fn = make_llm_policy(spec, log_dir=out / "transcripts")
            for r in range(args.runs):
                all_rows += run_policy(f"llm:{spec}", fn, tier, seeds, run_idx=r)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out / f"eval-{stamp}.jsonl").write_text("\n".join(json.dumps(r) for r in all_rows) + "\n")

    print(f"\n{'tier':<8}{'policy':<28}{'runs':>5}{'mean':>8}{'sd(run)':>9}{'solved%':>9}{'targets':>9}")
    keys = sorted({(r["tier"], r["policy"]) for r in all_rows}, key=lambda k: (args.tiers.split(",").index(k[0]), k[1]))
    for tier, pol in keys:
        rs = [r for r in all_rows if r["tier"] == tier and r["policy"] == pol]
        by_run = {}
        for r in rs:
            by_run.setdefault(r["run"], []).append(r["score"])
        run_means = [statistics.mean(v) for v in by_run.values()]
        sd = statistics.stdev(run_means) if len(run_means) > 1 else 0.0
        solved = 100 * sum(r["targets_completed"] == r["targets_total"] for r in rs) / len(rs)
        tgt = statistics.mean(r["targets_completed"] for r in rs)
        print(f"{tier:<8}{pol:<28}{len(by_run):>5}{statistics.mean(run_means):>8.3f}{sd:>9.3f}{solved:>8.0f}%{tgt:>9.2f}")
    print(f"\nraw results: {out / f'eval-{stamp}.jsonl'}")


if __name__ == "__main__":
    main()
