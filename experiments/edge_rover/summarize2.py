"""Rover v2 table: success rate + Wilson 95% CI per (model, controls), and paired McNemar vs a reference model.

    python summarize2.py results/*.jsonl --ref base --out results/SUMMARY.md
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from math import comb
from pathlib import Path

from summarize import wilson


def mcnemar(b: int, c: int) -> float:
    n = b + c
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n) if n else 1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--ref", default="base")
    ap.add_argument("--out")
    a = ap.parse_args()
    data = defaultdict(dict)  # (model, controls) -> seed -> row
    for f in a.files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            data[(r["model"], r["controls"])][r["seed"]] = r
    out = ["| model | controls | missions | success | 95% CI | beacon found | mean bumps | invalid replies | vs "
           f"{a.ref} (paired: better / worse, McNemar p) |", "|---|---|---|---|---|---|---|---|---|"]
    for (m, c) in sorted(data, key=lambda k: (k[1], k[0])):
        rows = data[(m, c)]
        n = len(rows)
        s = sum(r["success"] for r in rows.values())
        lo, hi = wilson(s, n)
        ref = data.get((a.ref, c), {})
        common = sorted(set(rows) & set(ref))
        if m != a.ref and common:
            b = sum(rows[x]["success"] and not ref[x]["success"] for x in common)
            w = sum(ref[x]["success"] and not rows[x]["success"] for x in common)
            cmp = f"{b} / {w}, p={mcnemar(b, w):.3g} (n={len(common)})"
        else:
            cmp = "-"
        out.append(f"| {m} | {c} | {n} | {s}/{n} ({100 * s / n:.0f}%) | {100 * lo:.0f}-{100 * hi:.0f}% | "
                   f"{sum(r['found'] for r in rows.values())} | {sum(r['bumps'] for r in rows.values()) / n:.1f} | "
                   f"{sum(r['invalid'] for r in rows.values())} | {cmp} |")
    text = "\n".join(out)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
