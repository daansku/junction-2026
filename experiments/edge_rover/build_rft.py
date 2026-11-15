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
    a = ap.parse_args()
    eps = [json.loads(l) for f in a.files for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
    solved = sorted((e for e in eps if e["solved"]), key=lambda e: -e["reward"])
    rows = []
    for e in solved:
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
             "examples": len(rows), "games": len({e["game_id"] for e in solved}),
             "levels": dict(Counter(e["level"] for e in solved))}
    Path(a.out + ".manifest.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
