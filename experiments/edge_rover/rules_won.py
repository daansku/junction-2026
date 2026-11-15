import json, sys, collections
sys.path[:0] = ["repo/arena/src", "repo/engine/src"]
from engine import list_games
meta = {m["game_id"]: m for m in list_games("repo/data/collections/train-v1.json")}
rounds = {"R1": ["rollouts/b200-try1.jsonl", "rollouts/b200-try2.jsonl", "rollouts/b200-v3.jsonl", "rollouts/h100.jsonl"],
          "R2": ["rollouts/r2.jsonl"], "R3": ["rollouts/r3.jsonl"]}
seen = set()
tot = collections.Counter()
for rn, files in rounds.items():
    won, played = {}, collections.Counter()
    for f in files:
        for l in open(f):
            e = json.loads(l)
            rules = tuple(meta[e["game_id"]]["rules_per_level"][e["level"] - 1]) or ("none",)
            played[rules] += 1
            k = (e["game_id"], e["level"])
            if e["solved"] and k not in seen:
                won[k] = rules
    seen |= set(won)
    c = collections.Counter(won.values())
    tot.update(c)
    print(f"{rn}: {len(won)} new levels won; by mechanics: " + ", ".join(f"{'+'.join(r)} {n}" for r, n in c.most_common()))
print("ALL unique wins by mechanics:", ", ".join(f"{'+'.join(r)} {n}" for r, n in tot.most_common()))
