"""Per-level stats for the /challenge demo, from recorded runs on the shared server.

Usage (repo root):
    python web/scripts/challenge_stats.py --api https://<host> --game gridworld-s1000-d1-l6-9b1065f8 --levels 3

Writes web/public/challenge/<game_id>.json, which /challenge loads for the end screen
("average over all recorded attempts"). The ghost race itself uses /games/{id}/ghosts live.

Per level, per run: solved (did the level counter advance), actions spent on that level
(every action counts, RESET included, same as the arena score). Score per level is
min(1, optimal / actions) when solved, else 0 (PLAN-v1 §4.6). A run's challenge score is the
mean over the first N levels. Runs still in progress that have not finished the N levels yet
are skipped, so an unfinished attempt never counts as a failure. Challenge-mode visitor plays
(player.mode == "challenge") are skipped so the demo never feeds on itself.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Same filters as analysis/src/analysis/loader.py (clean_runs) so the demo matches the leaderboard.
PRACTICE_HUMAN_NAMES = {"", "anonymous", "anon", "test", "practice", "debug"}
INFRA_END_REASONS = {"idle_timeout", "server_shutdown", "error"}


def get(api: str, path: str):
    req = urllib.request.Request(f"{api}{path}", headers={"User-Agent": "challenge-stats"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = r.read().decode()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def unwrap(v, key):
    if isinstance(v, list):
        return v
    for k in (key, "items", "data", "results"):
        if isinstance(v.get(k), list):
            return v[k]
    return []


def per_level(steps: list[dict], n_levels: int, start: int = 1) -> list[dict]:
    """[{level, solved, actions}] for levels start..start+n_levels-1, from a run's steps."""
    window = range(start, start + n_levels)
    out = {lv: {"level": lv, "solved": False, "actions": 0} for lv in window}
    prev_level = 1
    for st in steps:
        lv_after = int((st.get("truth") or {}).get("level") or prev_level)
        if st.get("action") is None:
            prev_level = lv_after
            continue
        if prev_level in out and not out[prev_level]["solved"]:
            out[prev_level]["actions"] += 1
            if lv_after > prev_level or (st.get("truth") or {}).get("state") == "WIN":
                out[prev_level]["solved"] = True
        prev_level = lv_after
    return [out[lv] for lv in window]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="server origin, e.g. https://host (no /api)")
    ap.add_argument("--game", required=True)
    ap.add_argument("--levels", type=int, default=3)
    ap.add_argument("--start", type=int, default=1, help="first level of the challenge window")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    api = a.api.rstrip("/") + "/api"
    n, start = a.levels, a.start

    game = get(api, f"/games/{a.game}")
    optimal = [int(lv["optimal_moves"]) for lv in game["levels"][start - 1:start - 1 + n]]
    runs = unwrap(get(api, f"/runs?game_id={a.game}&limit=5000"), "runs")

    players: dict[str, dict] = defaultdict(lambda: {"attempts": []})
    # Human baseline counts first attempts only (repeats know the level): keep each person's earliest run.
    seen_humans: set[str] = set()
    for r in sorted(runs, key=lambda x: x["run_id"]):
        p = r.get("player") or {}
        kind = p.get("kind")
        if kind not in ("model", "human") or p.get("mode") == "challenge":
            continue
        if r.get("start_level") or r.get("takeover_of"):
            continue
        if kind == "human" and str(p.get("name", "")).strip().lower() in PRACTICE_HUMAN_NAMES:
            continue
        if str(r.get("end_reason") or "").lower() in INFRA_END_REASONS:
            continue
        if kind == "model" and r.get("outcome") == "ABORTED":
            continue
        lc = int(r.get("levels_completed") or 0)
        if r.get("outcome") in (None, "IN_PROGRESS") and lc < start - 1 + n:
            continue  # not finished with the challenge window yet
        if (r.get("actions") or 0) == 0:
            continue
        if kind == "human":
            who = str(p.get("name", "")).strip().lower()
            if who in seen_humans:
                continue
            seen_humans.add(who)
        steps = unwrap(get(api, f"/runs/{r['run_id']}/steps"), "steps")
        if lc < start - 1:
            continue  # never reached the window: says nothing about these levels
        levels = per_level(steps, n, start)
        if kind == "human" and levels[0]["actions"] < 3 and not levels[0]["solved"]:
            continue  # opened the page and left
        scores = [min(1.0, optimal[i] / lv["actions"]) if lv["solved"] and lv["actions"] else 0.0
                  for i, lv in enumerate(levels)]
        # h2 (lab-style harness) runs are their own row, never merged with the same model on h1
        hv = r.get("harness_version") or p.get("harness_version") or "h1"
        key = "human" if kind == "human" else (p.get("model_id") or p.get("name")) + ("" if hv == "h1" else f"@{hv}")
        entry = players[key]
        entry.update({"kind": kind, "name": "People (first attempts)" if kind == "human" else (p.get("name") or key) + ("" if hv == "h1" else f" · {hv}"),
                      "model_id": None if kind == "human" else key})
        entry["attempts"].append({"run_id": r["run_id"], "levels": levels,
                                  "score": round(100 * sum(scores) / n, 1),
                                  "cleared": sum(1 for lv in levels if lv["solved"])})
        print(f"{key:32s} {r['run_id']} cleared={entry['attempts'][-1]['cleared']} "
              f"score={entry['attempts'][-1]['score']}", file=sys.stderr)

    rows = []
    for key, e in players.items():
        att = e["attempts"]
        rows.append({
            "id": key, "kind": e["kind"], "name": e["name"], "model_id": e["model_id"],
            "attempts": len(att),
            "mean_score": round(sum(x["score"] for x in att) / len(att), 1),
            "best_score": max(x["score"] for x in att),
            "cleared_all_rate": round(sum(1 for x in att if x["cleared"] == n) / len(att), 3),
            "per_level_solve_rate": [round(sum(1 for x in att if x["levels"][i]["solved"]) / len(att), 3)
                                     for i in range(n)],
            "runs": att,
        })
    rows.sort(key=lambda r: (r["kind"] != "human", -r["mean_score"]))
    doc = {
        "game_id": a.game, "levels": n, "start_level": start, "optimal_moves": optimal,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": a.api, "score_rule": "per level min(1, optimal/actions) if solved else 0; mean x 100",
        "players": rows,
    }
    out = Path(a.out) if a.out else Path(__file__).resolve().parents[1] / "public" / "challenge" / (f"{a.game}.json" if start == 1 else f"{a.game}-from{start}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {out} ({len(rows)} players)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
