"""Summarize paired rover results and write a short report using only stdlib."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean


def read(path: str) -> dict[int, dict]:
    return {int(row["seed"]): row for row in
            (json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines())}


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    p = successes / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return mid - half, mid + half


def fmt(rows: dict[int, dict]) -> dict:
    vals = list(rows.values())
    n = len(vals)
    successes = sum(x["success"] for x in vals)
    low, high = wilson(successes, n)
    return {"episodes": n, "successes": successes, "success_rate": successes / n if n else 0,
            "success_95ci": [low, high], "found": sum(x["found_beacon"] for x in vals),
            "mean_bumps": mean(x["bumps"] for x in vals) if n else 0,
            "mean_steps": mean(x["steps"] for x in vals) if n else 0,
            "invalid_replies": sum(x["invalid_replies"] for x in vals)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--tuned", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base, tuned = read(a.base), read(a.tuned)
    seeds = sorted(set(base) & set(tuned))
    b, t = {s: base[s] for s in seeds}, {s: tuned[s] for s in seeds}
    improved = sum(not b[s]["success"] and t[s]["success"] for s in seeds)
    regressed = sum(b[s]["success"] and not t[s]["success"] for s in seeds)
    discordant = improved + regressed
    mcnemar_p = min(1.0, 2 * sum(__import__("math").comb(discordant, k)
                                  for k in range(min(improved, regressed) + 1)) / (2 ** discordant)) if discordant else 1.0
    result = {"base": fmt(b), "tuned": fmt(t), "paired_seeds": len(seeds),
              "paired_improvements": improved, "paired_regressions": regressed,
              "mcnemar_exact_two_sided_p": mcnemar_p}
    Path(a.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
