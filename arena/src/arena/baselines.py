"""Baseline players. `random` and `optimal` are leaderboard reference rows;
`noop` and `stop_early` are the AfterQuery judging baselines (do-nothing, stop-early)."""
from __future__ import annotations

import random
import time

from .agent_loop import HARNESS_VERSION, GameResult, _outcome
from .client import GameClient

MOVE_ACTIONS = ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]


def _finish(session, truth, reason) -> None:
    session.end(reason, outcome=_outcome(truth, reason), usage_total={"in": 0, "out": 0, "cost_usd": 0.0})


def _result(session, game_id, truth, actions, t0, reason) -> GameResult:
    done = (truth.get("level", 1) - 1) + (1 if truth.get("state") == "WIN" else 0)
    return GameResult(run_id=session.run_id, game_id=game_id, outcome=_outcome(truth, reason),
                      levels_completed=done, levels_total=truth.get("levels_total", 0), actions=actions,
                      turns=actions, invalid_replies=0, tokens_in=0, tokens_out=0, cost_usd=0.0,
                      cost_known=True, wall_s=round(time.time() - t0, 1), reason=reason)


def _player(name: str) -> dict:
    return {"kind": "baseline", "name": name, "model_id": f"baseline:{name}", "harness_version": HARNESS_VERSION}


def play_random(client: GameClient, game_id: str, *, run_key=None, max_actions=400, seed=0, **_) -> GameResult:
    rng = random.Random(seed)
    session, start = client.start(game_id, _player("random"), run_key=run_key)
    allowed = start.get("available_actions") or ["RESET"] + MOVE_ACTIONS
    moves = [a for a in allowed if a not in ("RESET", "ACTION6", "ACTION7")]
    t0, n, truth = time.time(), 0, session.truth()
    while truth.get("state") != "WIN" and n < max_actions:
        a = "RESET" if truth.get("state") == "GAME_OVER" else rng.choice(moves)
        session.act(a)
        n += 1
        truth = session.truth()
    reason = "win" if truth.get("state") == "WIN" else "budget_actions"
    _finish(session, truth, reason)
    return _result(session, game_id, truth, n, t0, reason)


def play_optimal(client: GameClient, game_id: str, *, run_key=None, **_) -> GameResult:
    """Replays the engine's optimal path for every level, read from GET /games/{id}."""
    desc = client.describe(game_id)
    session, _ = client.start(game_id, _player("optimal"), run_key=run_key)
    t0, n = time.time(), 0
    for lv in desc.get("levels", []):
        for a in lv.get("optimal_path") or lv.get("optimal") or []:
            session.act(a)
            n += 1
    truth = session.truth()
    reason = "win" if truth.get("state") == "WIN" else "optimal_path_failed"
    _finish(session, truth, reason)
    return _result(session, game_id, truth, n, t0, reason)


def play_noop(client: GameClient, game_id: str, *, run_key=None, **_) -> GameResult:
    session, _ = client.start(game_id, _player("noop"), run_key=run_key)
    truth = session.truth()
    _finish(session, truth, "noop")
    return _result(session, game_id, truth, 0, time.time(), "noop")


def play_stop_early(client: GameClient, game_id: str, *, run_key=None, k=5, seed=0, **_) -> GameResult:
    rng = random.Random(seed)
    session, _ = client.start(game_id, _player("stop_early"), run_key=run_key)
    t0 = time.time()
    for _ in range(k):
        session.act(rng.choice(MOVE_ACTIONS))
    truth = session.truth()
    _finish(session, truth, "stop_early")
    return _result(session, game_id, truth, k, t0, "stop_early")


BASELINES = {"random": play_random, "optimal": play_optimal, "noop": play_noop, "stop_early": play_stop_early}
