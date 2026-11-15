"""Round-2 episode list: every level solved in round 1 gets 4 attempts; every other level with optimal <= 8 gets 1."""
import json, sys
sys.path[:0] = ["repo/arena/src", "repo/engine/src"]
from engine import list_games
won = set()
for f in sys.argv[1:]:
    for l in open(f):
        e = json.loads(l)
        if e["solved"]:
            won.add((e["game_id"], e["level"]))
rows = [{"game_id": g, "level": lv, "k": 4} for g, lv in sorted(won)]
for m in list_games("repo/data/collections/train-v1.json"):
    for i, o in enumerate(m["optimal_moves"]):
        if o <= 8 and (m["game_id"], i + 1) not in won:
            rows.append({"game_id": m["game_id"], "level": i + 1, "k": 1})
open("r2_episodes.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
print(len(won), "round-1 wins x4 +", len(rows) - len(won), "other easy levels =", sum(r["k"] for r in rows), "episodes")
