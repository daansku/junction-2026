"""Held-out MATH comparison: a candidate run vs base, paired per item (PROTOCOL amendment v5).

    python bench/heldout_math/compare.py <candidate run dir | items jsonl> [--base <run dir | items jsonl>]

The base defaults to bench/heldout_math/base_math_items.jsonl (Qwen3.5-9B, the scores behind the S5 numbers).
A run dir is read from items_v3.jsonl (after posttrain.rescore_answer) or else items.jsonl; only `math` rows count.

For each half of the 350 MATH items (50 per subject, doc 0-49) prints: base and candidate accuracy, delta,
paired-bootstrap 95% CI (bench.stats, 10,000 resamples, seed 20261114), exact McNemar p (two-sided, discordant items)
and a paired sign-flip permutation p (100,000, seed 20261115).
  HELD-OUT       doc 25-49 per subject (175 items): the number to report
  selection half doc 0-24 per subject (175 items): the dev slice used to pick checkpoints, label it "used for selection"
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from bench import stats  # noqa: E402


def load(path: str) -> dict[str, float]:
    p = Path(path)
    if p.is_dir():
        p = p / "items_v3.jsonl" if (p / "items_v3.jsonl").exists() else p / "items.jsonl"
    out = {}
    for line in p.open(encoding="utf-8"):
        it = json.loads(line)
        if it["bench"] == "math":
            out[it["item"]] = float(it.get("score_v3", it["score"]))
    return out


def mcnemar_exact(up: int, down: int) -> float:
    n = up + down
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(up, down) + 1)) / 2 ** n)


def perm_p(diffs: list[float], n_perm: int = 100_000, seed: int = 20261115) -> float:
    obs = abs(sum(diffs))
    rng = random.Random(seed)
    hits = sum(abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= obs - 1e-12 for _ in range(n_perm))
    return (hits + 1) / (n_perm + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cand")
    ap.add_argument("--base", default=str(HERE / "base_math_items.jsonl"))
    a = ap.parse_args()
    base, cand = load(a.base), load(a.cand)
    print(f"base: {a.base} ({len(base)} math items)\ncandidate: {a.cand} ({len(cand)} math items)")
    for label, lo, hi in (("HELD-OUT (doc 25-49, report this)", 25, 49), ("selection half (doc 0-24)", 0, 24)):
        keys = [k for k in cand if k in base and lo <= int(k.rsplit(":", 1)[1]) <= hi]
        if not keys:
            print(f"{label}: no shared items")
            continue
        r = stats.paired_delta({k: base[k] for k in keys}, {k: cand[k] for k in keys})
        up = sum(cand[k] > base[k] for k in keys)
        down = sum(cand[k] < base[k] for k in keys)
        diffs = [cand[k] - base[k] for k in keys]
        print(f"{label}: n={r['n_shared']} base={r['mean_a']:.3f} cand={r['mean_b']:.3f} delta={r['delta']:+.3f} "
              f"95% CI [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] | only cand right {up}, only base right {down} | "
              f"McNemar p={mcnemar_exact(up, down):.3f} | permutation p={perm_p(diffs):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
