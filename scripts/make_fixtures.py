"""Regenerate data/fixtures/ from the fake engine. Deterministic: rerunning gives identical files.

    python scripts/make_fixtures.py

Writes:
  data/fixtures/frames/{initial,mid,game_over,win}.json   single frames (64 hex rows)
  data/fixtures/games.json                                 catalogue of 3 games (GET /api/games)
  data/fixtures/games/<game_id>.json                       describe() per game (GET /api/games/{id})
  data/fixtures/runs/<run_id>/meta.json + steps.jsonl      one complete 30-step model run with reasoning
  data/fixtures/runs.json                                  list of run metas (GET /api/runs)
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "src"))

from server.fake_engine import DEV_SPECS, Action, FakeGame, list_games  # noqa: E402

OUT = ROOT / "data" / "fixtures"
T0 = datetime(2026, 11, 14, 4, 30, 0, tzinfo=timezone.utc)


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8", newline="\n")


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def frames() -> None:
    g = FakeGame(DEV_SPECS[0])
    dump(OUT / "frames" / "initial.json", g.frame())
    path = g.describe()["levels"][0]["optimal_path"]
    for a in path[: len(path) // 2]:
        g.step(a)
    dump(OUT / "frames" / "mid.json", g.frame())
    g2 = FakeGame(DEV_SPECS[0])
    a, b = Action.ACTION3, Action.ACTION4      # shuffle left/right (or bump) until out of moves
    while g2.truth()["state"] == "NOT_FINISHED":
        g2.step(a)
        a, b = b, a
    assert g2.truth()["state"] == "GAME_OVER" and g2.truth()["level"] == 1
    dump(OUT / "frames" / "game_over.json", g2.frame())
    g3 = FakeGame(DEV_SPECS[0])
    for lv in g3.describe()["levels"]:
        for a in lv["optimal_path"]:
            g3.step(a)
    assert g3.truth()["state"] == "WIN"
    dump(OUT / "frames" / "win.json", g3.frame())


def games() -> list[dict]:
    cat = list_games("dev")
    for m in cat:
        m["thumbnail_url"] = f"/api/games/{m['game_id']}/thumbnail.png"
        dump(OUT / "games" / f"{m['game_id']}.json", FakeGame(DEV_SPECS[[x['game_id'] for x in cat].index(m['game_id'])]).describe())
    dump(OUT / "games.json", cat)
    return cat


OPPOSITE = {"ACTION1": "ACTION2", "ACTION2": "ACTION1", "ACTION3": "ACTION4", "ACTION4": "ACTION3"}
NAMES = {"ACTION1": "up", "ACTION2": "down", "ACTION3": "left", "ACTION4": "right", "RESET": "reset"}


def scripted_actions(desc: dict) -> list[str]:
    """Plausible model play: explores, bumps a wall, solves level 1, wanders on level 2, resets, retries."""
    l1 = desc["levels"][0]["optimal_path"]
    l2 = desc["levels"][1]["optimal_path"]
    acts = [OPPOSITE[l1[0]], l1[0]] + list(l1)          # one wasted step back-and-forth
    acts += [OPPOSITE[l2[0]]] * 3 + ["RESET"] + list(l2)
    l3 = desc["levels"][2]["optimal_path"]
    acts += list(l3)
    return acts[:30]


def reasoning_for(i: int, action: str, truth_before: dict, truth_after: dict) -> tuple[str, str, str]:
    ev = truth_after["events"]
    name = NAMES[action]
    if i == 1:
        return (f"First frame. A small blue square sits in a grid of grey blocks; there is one green square. "
                f"A yellow bar at the top may be a timer. Trying {name} to see what I control.",
                "I control the blue square", "playing")
    if action == "RESET":
        return ("I keep walking away from the green square and the yellow bar is shrinking. Restarting this layout "
                "to get the full bar back.", "RESET restores the level and refills the yellow bar", "playing")
    if "level_complete" in ev:
        return (f"Moved {name} onto the green square. The layout changed and a new pip lit at the top right, so "
                f"reaching green completes a level.", "reach the green square to finish the level; yellow bar = moves left", "playing")
    if "bump" in ev:
        return (f"Moved {name} but the blue square did not move. Grey blocks are walls. The yellow bar still shrank, "
                f"so bumping costs a move.", "grey blocks are walls; every action costs one unit of the yellow bar", "playing")
    if truth_after["level"] >= 2 and truth_after["moves_used"] <= 3 and truth_before["level"] == truth_after["level"] and i < 20:
        return (f"New layout. Testing {name} to check whether the controls are the same as before.",
                "controls are unchanged across levels", "playing")
    return (f"Heading {name} toward the green square along the open corridor.",
            "reach the green square to finish the level; yellow bar = moves left", "playing")


def run() -> dict:
    spec = DEV_SPECS[1]
    g = FakeGame(spec)
    desc = g.describe()
    run_id = "fixture-run-0001"
    player = {"kind": "model", "name": "Mock Model", "model_id": "mock-model", "provider": "mock", "effort": "medium"}
    steps = [{"i": 0, "t_ms": 0, "action": None, "frame": g.frame(), "truth": g.truth(),
              "reasoning": None, "hypothesis": None, "belief": None, "usage": {"in": 0, "out": 0, "cost_usd": 0.0},
              "latency_ms": None}]
    t_ms, tin, tout, cost = 0, 0, 0, 0.0
    for i, action in enumerate(scripted_actions(desc), start=1):
        before = g.truth()
        g.step(action)
        after = g.truth()
        reasoning, hyp, belief = reasoning_for(i, action, before, after)
        u_in, u_out = 1800 + 140 * i, 120 + (i * 37) % 90
        c = round(u_in * 1e-6 + u_out * 5e-6, 6)
        lat = 700 + (i * 113) % 900
        t_ms += lat + 50
        tin, tout, cost = tin + u_in, tout + u_out, cost + c
        steps.append({"i": i, "t_ms": t_ms, "action": action, "frame": g.frame(), "truth": after,
                      "reasoning": reasoning, "hypothesis": hyp, "belief": belief,
                      "usage": {"in": u_in, "out": u_out, "cost_usd": c}, "latency_ms": lat})
    final = g.truth()
    levels_completed = final["level"] - 1 + (1 if final["state"] == "WIN" else 0)
    meta = {
        "run_id": run_id, "run_key": "fixture", "game_id": g.game_id, "collection": "dev", "split": "dev",
        "player": player, "harness_version": "h1", "engine_version": desc["engine_version"],
        "started_at": iso(T0), "ended_at": iso(T0 + timedelta(milliseconds=t_ms)),
        "outcome": "BUDGET" if final["state"] == "NOT_FINISHED" else final["state"],
        "end_reason": "action budget reached (30)" if final["state"] == "NOT_FINISHED" else None,
        "levels_completed": levels_completed, "levels_total": final["levels_total"],
        "actions": len(steps) - 1, "resets": final["resets"],
        "tokens_in": tin, "tokens_out": tout, "cost_usd": round(cost, 6), "wall_s": round(t_ms / 1000, 3),
    }
    d = OUT / "runs" / run_id
    dump(d / "meta.json", meta)
    (d / "steps.jsonl").write_text("".join(json.dumps(s) + "\n" for s in steps), encoding="utf-8", newline="\n")
    dump(OUT / "runs.json", [meta])
    return meta


def main() -> None:
    for sub in ("frames", "games", "runs"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
    frames()
    games()
    meta = run()
    print(f"fixtures written to {OUT}: run outcome={meta['outcome']} levels={meta['levels_completed']}/{meta['levels_total']}")


if __name__ == "__main__":
    main()
