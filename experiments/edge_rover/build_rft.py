"""Expert-iteration RL, step 2: keep only episodes that SOLVED their level (outcome reward > 0) and turn every
valid turn of them into an SFT example of the policy's own reply (thinking + JSON). Failed episodes contribute
nothing. Higher-reward (more efficient) episodes are taken first if --max-examples caps the set.

    python build_rft.py rollouts/a100.jsonl rollouts/h100.jsonl --out rft.jsonl --max-examples 600
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-examples", type=int, default=600)
    ap.add_argument("--min-reward", type=float, default=0.0, help="keep only wins at least this efficient")
    ap.add_argument("--rule-oversample", type=int, default=1, help="repeat rule-level (level > 1) episodes this many times")
    ap.add_argument("--eff-dup", type=float, default=None, help="wins with reward >= this are repeated twice")
    a = ap.parse_args()
    eps = [json.loads(l) for f in a.files for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
    # No memorisation: each (game, level) contributes at most ONE win, from the earliest file (round) that won it.
    # A later round replaying a level the model already trained on is dropped, so no level is trained on twice.
    # Multiple shots per level are allowed: within the first round (file) that won a level, keep its BEST shot.
    first, first_file, replays = {}, {}, 0
    for fi, f in enumerate(a.files):
        for l in Path(f).read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            e = json.loads(l)
            if not e["solved"]:
                continue
            k = (e["game_id"], e["level"])
            if k not in first:
                first[k], first_file[k] = e, fi
            elif first_file[k] == fi:  # another shot in the same round: keep the more efficient win
                if e["reward"] > first[k]["reward"]:
                    first[k] = e
            else:
                replays += 1  # a later round re-winning an already-trained level: never trained twice
    solved = sorted((e for e in first.values() if e["reward"] >= a.min_reward), key=lambda e: -e["reward"])
    weighted = []
    for e in solved:
        n = (a.rule_oversample if e["level"] > 1 else 1) * (2 if a.eff_dup is not None and e["reward"] >= a.eff_dup else 1)
        weighted += [e] * n
    rows = []
    for e in weighted:
        for t in e["turns"]:
            if not t["valid"]:
                continue
            reply = t["reply"]
            content = reply if reply.lstrip().startswith("<think>") else "<think>\n" + reply.lstrip()
            rows.append({"messages": [{"role": "system", "content": e["system"]},
                                      {"role": "user", "content": t["user"]},
                                      {"role": "assistant", "content": content}],
                         "meta": {"game_id": e["game_id"], "level": e["level"], "reward": e["reward"]}})
        if len(rows) >= a.max_examples:
            break
    Path(a.out).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    stats = {"episodes": len(eps), "solved": len(solved), "solve_rate": round(len(solved) / max(len(eps), 1), 3),
             "mean_reward_solved": round(sum(e["reward"] for e in solved) / max(len(solved), 1), 3),
             "examples": len(rows), "weighted_episodes": len(weighted), "dropped_replays": replays, "unique_levels_won": len(first), "games": len({e["game_id"] for e in solved}),
             "levels": dict(Counter(e["level"] for e in solved))}
    Path(a.out + ".manifest.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
