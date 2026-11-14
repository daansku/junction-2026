import re
from pathlib import Path

import pytest

from engine import Action, Game, GameSpec, make_game
from engine.cli import verify_game
from engine.solver import random_walk_win_rate, solve

SRC = Path(__file__).resolve().parents[1] / "src" / "engine"


@pytest.fixture(scope="module")
def game():
    return make_game(GameSpec(seed=1234, n_levels=3, difficulty=2))


def test_frame_shape(game):
    f = game.reset()
    assert len(f) == 64
    assert all(len(r) == 64 and re.fullmatch(r"[0-9a-f]{64}", r) for r in f)


def test_deterministic():
    a = make_game(GameSpec(seed=99, n_levels=3))
    b = make_game(GameSpec(seed=99, n_levels=3))
    assert a.game_id == b.game_id
    assert a.reset() == b.reset()
    for act in a.levels[0].optimal_path[:5]:
        assert a.step(act) == b.step(act)
    assert a.state_hash() == b.state_hash()


def test_different_seeds_differ():
    assert make_game(GameSpec(seed=1, n_levels=2)).game_id != make_game(GameSpec(seed=2, n_levels=2)).game_id


def test_optimal_paths_win(game):
    game.reset()
    for i, lv in enumerate(game.levels):
        assert 0 < lv.optimal_moves <= lv.move_budget
        for act in lv.optimal_path:
            game.step(act)
        assert game.truth()["levels_completed"] == i + 1
    assert game.truth()["state"] == "WIN"
    frame = game.frame()
    assert game.step(Action.ACTION1) == frame        # nothing changes after WIN
    assert game.available_actions() == []


def test_solver_matches_stored_optimum(game):
    for lv in game.levels:
        assert len(solve(lv)) == lv.optimal_moves


def test_budget_game_over_and_reset(game):
    game.reset()
    for _ in range(game.levels[0].move_budget):
        game.step(Action.ACTION1)  # bumping still costs moves
    t = game.truth()
    assert t["state"] == "GAME_OVER" and t["moves_used"] == t["move_budget"]
    f = game.frame()
    for a in (Action.ACTION2, Action.ACTION3, Action.ACTION5):
        assert game.step(a) == f
    game.step(Action.RESET)
    t = game.truth()
    assert t["state"] == "NOT_FINISHED" and t["moves_used"] == 0 and t["resets"] == 1


def test_unavailable_action_is_free(game):
    game.reset()
    game.step(Action.ACTION5)   # no interact component in a tier-0 game
    assert game.truth()["moves_used"] == 0


def test_random_walk_rarely_wins(game):
    for lv in game.levels:
        assert random_walk_win_rate(lv, tries=200, seed="test") < 0.02


def test_serialisation_roundtrip(game):
    g2 = Game.from_dict(game.to_dict())
    assert g2.game_id == game.game_id and g2.reset() == game.reset()
    assert verify_game(game.to_dict()) == []


def test_clone_independent(game):
    game.reset()
    c = game.clone()
    c.step(game.levels[0].optimal_path[0])
    assert c.state_hash() != game.state_hash()


def test_no_global_random_or_builtin_hash():
    for p in SRC.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        # random.Random(seed) instances are fine; the module-level global stream is not
        assert not re.search(r"\brandom\.(random|randint|choice|choices|shuffle|seed|sample|uniform)\(", text), p
        assert not re.search(r"(?<![\w.`])hash\(", text), p


def test_deterministic_across_processes():
    """Different PYTHONHASHSEED must give byte-identical games (no builtin hash() leaks)."""
    import os
    import subprocess
    import sys
    code = ("from engine import make_game, GameSpec; g = make_game(GameSpec(seed=31, difficulty=3)); "
            "print(g.game_id, g.state_hash())")
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={**os.environ, "PYTHONHASHSEED": str(h)}).stdout for h in (1, 2)}
    assert len(outs) == 1 and next(iter(outs)).startswith("gridworld-s31")
