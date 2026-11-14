"""Statistics for bench results: per-benchmark means with bootstrap CIs, and paired deltas.

Everything works on per-item scores: {benchmark: {item_id: score}} where score is in [0, 1]
(the mean over samples when an item was sampled more than once). Pure Python, seeded, deterministic.
"""
from __future__ import annotations

import random
from typing import Mapping

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 20261114


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def mean_ci(scores: list[float], resamples: int = DEFAULT_RESAMPLES, seed: int = DEFAULT_SEED,
            alpha: float = 0.05) -> dict:
    """Mean of per-item scores with a percentile bootstrap CI over items."""
    n = len(scores)
    if n == 0:
        return {"n": 0, "mean": None, "ci_low": None, "ci_high": None}
    rng = random.Random(seed)
    m = sum(scores) / n
    boots = sorted(sum(scores[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return {"n": n, "mean": m, "ci_low": _quantile(boots, alpha / 2), "ci_high": _quantile(boots, 1 - alpha / 2)}


def paired_delta(a: Mapping[str, float], b: Mapping[str, float], resamples: int = DEFAULT_RESAMPLES,
                 seed: int = DEFAULT_SEED, alpha: float = 0.05) -> dict:
    """Paired bootstrap of mean(b - a) over the items both runs scored.

    `a` is the reference (base or ctrl), `b` the candidate. Items missing from either side are
    dropped and counted, never imputed. `excludes_zero` is the test the protocol uses.
    """
    shared = sorted(set(a) & set(b))
    diffs = [float(b[k]) - float(a[k]) for k in shared]
    n = len(diffs)
    out = {"n_shared": n, "n_only_a": len(set(a) - set(b)), "n_only_b": len(set(b) - set(a))}
    if n == 0:
        return {**out, "delta": None, "ci_low": None, "ci_high": None, "excludes_zero": False}
    rng = random.Random(seed)
    d = sum(diffs) / n
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    lo, hi = _quantile(boots, alpha / 2), _quantile(boots, 1 - alpha / 2)
    return {**out, "delta": d, "ci_low": lo, "ci_high": hi, "excludes_zero": lo > 0 or hi < 0,
            "mean_a": sum(float(a[k]) for k in shared) / n, "mean_b": sum(float(b[k]) for k in shared) / n}


def tier_mean(per_bench: Mapping[str, Mapping[str, float]], benches: list[str]) -> dict:
    """Unweighted mean over benchmarks of a tier (each benchmark counts once, whatever its size)."""
    means = [sum(v.values()) / len(v) for k, v in per_bench.items() if k in benches and v]
    return {"benchmarks": len(means), "mean": sum(means) / len(means) if means else None}
