"""Interaction audit: how close does a player who never uses a level's rule get to optimal?

  python engine/tools/interaction_audit.py --collection eval-v1 [--max-games 30] [--out audit.json]
  python engine/tools/interaction_audit.py --family gridforce --difficulty 2 --seeds 5000:5020

Per (level, rule): rule kind (use / avoid / builtin / constraint, see generator/interaction.py),
optimal length, avoid-optimal length (use rules: best win that never triggers the rule) or
ignorant-optimal length (avoid rules: optimum with the rule removed), avoider score bound
(optimal / avoid_optimal, 0 if avoiding is impossible), forced yes/no. Summary per rule and
for teaching levels (the level that introduces the rule).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict

from engine import GameSpec, load_collection, make_game
from engine.core.level import Level
from engine.generator import interaction as I


def audit_levels(games):
    rows = []
    for gid, levels in games:
        for i, lv in enumerate(levels):
            for rule, r in I.level_report(lv).items():
                rows.append({"game_id": gid, "level": i + 1, "rule": rule, "optimal": lv.optimal_moves, **r})
    return rows


def summary(rows):
    by = defaultdict(list)
    for r in rows:
        if r["kind"] in ("use", "avoid"):
            by[(r["rule"], r["new"])].append(r)
    out = {}
    for (rule, new), rs in sorted(by.items()):
        sc = [r["avoider_score"] for r in rs if r.get("avoider_score") is not None]
        out[f"{rule}{' (new)' if new else ''}"] = {
            "n": len(rs), "kind": rs[0]["kind"],
            "forced_pct": round(100 * sum(r["forced"] for r in rs) / len(rs)),
            "avoider_ge_0.8_pct": round(100 * sum(x >= 0.8 for x in sc) / len(sc)) if sc else None,
        }
    use = [r["avoider_score"] for r in rows if r["kind"] == "use" and r.get("avoider_score") is not None]
    new = [r for r in rows if r["new"] and r["kind"] in ("use", "avoid")]
    out["_all"] = {
        "use_pairs": len(use),
        "use_avoider_ge_0.8_pct": round(100 * sum(x >= 0.8 for x in use) / len(use)) if use else None,
        "use_avoider_ge_0.5_pct": round(100 * sum(x >= 0.5 for x in use) / len(use)) if use else None,
        "new_rule_levels": len(new),
        "new_rule_forced_pct": round(100 * sum(r["forced"] for r in new) / len(new)) if new else None,
    }
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--collection")
    p.add_argument("--max-games", type=int, default=0)
    p.add_argument("--family", default="gridforce")
    p.add_argument("--difficulty", type=int, default=2)
    p.add_argument("--levels", type=int, default=6)
    p.add_argument("--seeds", default="5000:5010")
    p.add_argument("--out")
    a = p.parse_args(argv)
    t = time.time()
    if a.collection:
        col = load_collection(a.collection)
        gs = col["games"][: a.max_games or None]
        games = [(g["game_id"], [Level.from_dict(x) for x in g["levels"]]) for g in gs]
        label = a.collection
    else:
        lo, hi = (int(x) for x in a.seeds.split(":"))
        games = []
        for s in range(lo, hi):
            g = make_game(GameSpec(family=a.family, seed=s, difficulty=a.difficulty, n_levels=a.levels))
            games.append((g.game_id, g.levels))
        label = f"{a.family} d{a.difficulty} seeds {a.seeds}"
    rows = audit_levels(games)
    res = {"source": label, "games": len(games), "k": I.K, "force_version": I.FORCE_VERSION,
           "summary": summary(rows), "rows": rows}
    print(json.dumps({"source": label, "games": len(games), "seconds": round(time.time() - t, 1),
                      **res["summary"]["_all"]}))
    for k, v in res["summary"].items():
        if k != "_all":
            print(f"  {k:24} {v}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
