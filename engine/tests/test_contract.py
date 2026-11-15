"""Engine output must match contracts/engine_api.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from engine import GameSpec, list_games, make_game, render_png

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "contracts" / "engine_api.py"


@pytest.fixture(scope="module")
def api():
    if not API.exists():
        pytest.skip("contracts not present")
    spec = importlib.util.spec_from_file_location("engine_api", API)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_api"] = mod  # dataclasses need the module registered
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def game():
    return make_game(GameSpec(seed=5, n_levels=3, difficulty=1))


def test_frame_wire_format(api, game):
    api.validate_frame(game.reset())
    api.validate_frame(game.step("ACTION1"))


def test_truth_keys(api, game):
    t = game.truth()
    assert set(api.Truth.__annotations__) <= set(t)
    json.dumps(t)


def test_describe_keys(api, game):
    d = game.describe()
    assert set(api.Description.__annotations__) <= set(d)
    for lv in d["levels"]:
        assert set(api.LevelInfo.__annotations__) <= set(lv)
    json.dumps(d)


def test_spec_fields_match(api):
    assert set(api.GameSpec.__dataclass_fields__) == set(GameSpec.__dataclass_fields__)


def test_actions_match(api, game):
    from engine import Action
    assert [a.value for a in api.Action] == [a.value for a in Action]
    json.dumps(game.available_actions())


def test_png(game):
    assert render_png(game.frame()).startswith(b"\x89PNG")


def test_list_games_dev():
    if not (ROOT / "data" / "collections" / "dev.json").exists():
        pytest.skip("no dev collection")
    metas = list_games("dev")
    assert metas and all({"game_id", "spec", "levels_total"} <= set(m) for m in metas)
