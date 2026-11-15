"""Round-3 episode list: FRESH levels only. Levels with exactly 10 optimal moves were never played by rounds 1-2
(round 1: optimal <= 9; round 2: optimal <= 8 + replays). Deterministic sample of N levels, K shots each."""
import json, random, sys
sys.path[:0] = ["repo/arena/src", "repo/engine/src"]
from engine import list_games
n, k = int(sys.argv[1]), int(sys.argv[2])
played = set()
for f in sys.argv[3:]:
    for l in open(f):
        e = json.loads(l)
        played.add((e["game_id"], e["level"]))
cands = [(m["game_id"], i + 1) for m in list_games("repo/data/collections/train-v1.json")
         for i, o in enumerate(m["optimal_moves"]) if o == 10 and (m["game_id"], i + 1) not in played]
random.Random(20261115).shuffle(cands)
rows = [{"game_id": g, "level": lv, "k": k} for g, lv in sorted(cands[:n])]
open("r3_episodes.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
print(len(cands), "fresh optimal-10 levels available;", len(rows), "levels x", k, "shots =", len(rows) * k, "episodes")
