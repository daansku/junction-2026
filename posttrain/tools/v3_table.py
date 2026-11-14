"""Post-training table (PROTOCOL v3) on the dev-slice items, same items for every column.

    python3 posttrain/tools/v3_table.py /srv/bench/out > /srv/bench/out/v3_table.md

Columns: base, ctrl, games, mix, sft-v1, best RL (highest v3 headline among rl-* checkpoints; all RL rows listed below).
Reads items_v3.jsonl written by `python -m posttrain.rescore_answer`. Dev-slice item set = the items of a dev-slice run
(sft-games-dev-merged), i.e. the first 25 per (sub)task; full-suite rows are restricted to those items.
"""
from __future__ import annotations

import json
import os
import sys

PRIMARY = ["bbh", "math", "gsm8k", "medqa", "mmlu_pro_health", "mmlu_pro_law"]
CONTROL = "mmlu_pro_history"
COLS = [("base", ["base"]), ("ctrl", ["sft-ctrl"]), ("games", ["sft-games-dev-merged", "sft-games"]),
        ("mix", ["sft-mix"]), ("sft-v1", ["sft-v1"])]
REF = "sft-games-dev-merged"


def load(out, run):
    p = os.path.join(out, run, "items_v3.jsonl")
    return {r["item"]: r for r in map(json.loads, open(p, encoding="utf-8"))} if os.path.exists(p) else None


def scores(rows, ref):
    res = {}
    for b in PRIMARY + [CONTROL]:
        ks = [k for k, r in ref.items() if r["bench"] == b and k in rows]
        res[b] = (sum(rows[k]["score"] for k in ks) / len(ks), len(ks)) if ks else (None, 0)
    prim = [res[b][0] for b in PRIMARY]
    res["headline"] = (sum(prim) / len(prim), None) if all(x is not None for x in prim) else (None, None)
    return res


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/srv/bench/out"
    ref = load(out, REF)
    if ref is None:
        sys.exit(f"no {REF}/items_v3.jsonl")
    table = {}
    for col, cands in COLS:
        for run in cands:
            rows = load(out, run)
            if rows is not None and sum(k in rows for k in ref) >= 0.9 * len(ref):
                table[col] = (run, scores(rows, ref))
                break
    rl = {}
    for run in sorted(os.listdir(out)):
        if run.startswith("rl-") and (rows := load(out, run)) is not None:
            rl[run] = scores(rows, ref)
    if rl:
        best = max(rl, key=lambda r: rl[r]["headline"][0] if rl[r]["headline"][0] is not None else -1)
        table["best RL"] = (best, rl[best])
    names = [c for c, _ in COLS] + ["best RL"]
    fmt = lambda v: "-" if v is None else f"{v:.3f}"
    print("| v3, dev-slice items | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    print("| run | " + " | ".join(table[c][0] if c in table else "pending" for c in names) + " |")
    for b in ["headline"] + PRIMARY + [CONTROL]:
        label = "**headline (primary mean)**" if b == "headline" else (b + (" (neg. control)" if b == CONTROL else ""))
        print(f"| {label} | " + " | ".join(fmt(table[c][1][b][0]) if c in table else "-" for c in names) + " |")
    if rl:
        print("\nAll RL checkpoints (headline v3): " + ", ".join(f"{r[3:]} {fmt(v['headline'][0])}" for r, v in rl.items()))


if __name__ == "__main__":
    main()
