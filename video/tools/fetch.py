"""Cache real game material for the video from the live server.

Writes into video/cache/ (gitignored):
  runs.json              list of finished model runs (metadata only)
  steps/<run_id>.json    every step (frame, action, reasoning) of the replay runs
  wall/<run_id>.json     a sample of frames from other failed runs, for the "many agents" shots
  derived/*.json         copies of /api/derived/* used for on-screen numbers

Usage (from the repo root):
  video/.venv/python.exe video/tools/fetch.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "video" / "cache"
API = (ROOT / "coordination" / "API_URL").read_text().strip().rstrip("/") + "/api"

# Replay runs for S3 (picked from rules.json failure-mode examples).
REPLAYS = [
    "20261114T015741-02f65e44",  # Nemotron, hazards, no_effect_loop from step 16
    "20261114T015741-3858885a",  # Kimi K3.1, one_way, late_reset at step 123
    "20261114T015741-8260dc79",  # Kimi K3.1, push_blocks, belief_mismatch at step 109
]
WALL_RUNS = 48          # how many other failed runs to sample for the wall of agents
WALL_FRAMES = 24        # frames kept per wall run
DERIVED = ["leaderboard.json", "leaderboard_h2.json", "rules.json", "insights.json", "explanations.json"]


def get(path: str):
    req = urllib.request.Request(API + path, headers={"User-Agent": "video-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def save(rel: str, obj) -> None:
    p = CACHE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


def main() -> int:
    for name in DERIVED:
        try:
            save(f"derived/{name}", get(f"/derived/{name}"))
        except Exception as e:  # explanations.json may not exist yet
            print(f"skip derived/{name}: {e}")

    runs = [r for r in get("/runs?kind=model") if r.get("outcome") not in (None, "IN_PROGRESS")]
    save("runs.json", runs)
    print(f"{len(runs)} finished model runs")

    for rid in REPLAYS:
        steps = get(f"/runs/{rid}/steps")
        save(f"steps/{rid}.json", steps)
        print(f"replay {rid}: {len(steps)} steps")

    failed = [r for r in runs if r["outcome"] != "WIN" and r["actions"] >= 30 and r["run_id"] not in REPLAYS]
    for r in failed[:WALL_RUNS]:
        steps = get(f"/runs/{r['run_id']}/steps")
        k = max(1, len(steps) // WALL_FRAMES)
        sample = [{"i": s["i"], "frame": s["frame"], "action": s.get("action")} for s in steps[::k]][:WALL_FRAMES]
        save(f"wall/{r['run_id']}.json", {"meta": r, "frames": sample})
    print(f"wall: {min(len(failed), WALL_RUNS)} runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
