import json
import zlib

import pytest

from arena.agent_loop import Budgets, build_parts, parse_reply, play_model
from arena.baselines import BASELINES
from arena.client import MockClient
from arena.frames import diff_count, to_png, to_text, validate
from arena.mock_game import MockGame
from arena.providers.mock_provider import MockProvider
from arena.registry import load_models, usable
from arena.runner import execute, load_sweep, run_key

ALLOWED = ["RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4"]
GID = "mock-s1-l3"


def test_mock_frames_valid_and_deterministic():
    a, b = MockGame(3).reset(), MockGame(3).reset()
    validate(a)
    assert a == b


def test_png_is_valid():
    png = to_png(MockGame(0).reset(), scale=2)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert b"IEND" in png[-12:]
    # IDAT decompresses to (1 + 128) * 128 bytes
    i = png.index(b"IDAT")
    n = int.from_bytes(png[i - 4:i], "big")
    assert len(zlib.decompress(png[i + 4:i + 4 + n])) == 129 * 128


def test_text_grid_is_frame():
    f = MockGame(0).reset()
    assert to_text(f).splitlines() == f
    assert diff_count(f, f) == 0


@pytest.mark.parametrize("text,ok", [
    ('{"notes":"n","hypothesis":"h","belief":"playing","action":"action3"}', True),
    ('sure!\n```json\n{"action":"ACTION1"}\n```', True),
    ('{"action":"ACTION9"}', False),
    ("go left", False),
    ('{"action":', False),
])
def test_parse_reply(text, ok):
    d, err = parse_reply(text, ALLOWED)
    assert (d is not None) == ok
    if ok:
        assert d["action"] in ALLOWED and d["belief"] in ("playing", "won", "lost")


def test_prompt_never_contains_truth():
    g = MockGame(0)
    parts = build_parts(g.reset(), "notes", [("ACTION1", 3)], ALLOWED, ["image", "text"], 1)
    blob = json.dumps([p for p in parts if p["type"] == "text"])
    for leak in ("optimal", "move_budget", "WIN", "GAME_OVER", "active_rules", "level"):
        assert leak not in blob


def test_optimal_wins_and_noop_scores_nothing():
    c = MockClient()
    r = BASELINES["optimal"](c, GID)
    assert r.outcome == "WIN" and r.levels_completed == 3
    n = BASELINES["noop"](c, GID)
    assert n.levels_completed == 0 and n.actions == 0
    s = BASELINES["stop_early"](c, GID)
    assert s.levels_completed == 0 and s.actions == 5


def test_random_rarely_wins():
    c = MockClient()
    wins = sum(BASELINES["random"](c, GID, seed=i, max_actions=200).outcome == "WIN" for i in range(10))
    assert wins <= 2


def test_model_loop_with_mock_provider_and_invalid_replies():
    m = {"id": "mock", "display_name": "mock", "provider": "mock", "api_model": "mock", "input_modes": ["text"],
         "price_in": 1.0, "price_out": 2.0, "garbage_every": 4}
    c = MockClient()
    r = play_model(c, GID, MockProvider(m), m, effort=None, run_key="k", budgets=Budgets(max_actions=30, max_turns=40))
    assert r.actions == 30 and r.invalid_replies > 0 and r.turns > r.actions
    assert r.cost_usd > 0 and r.cost_known
    steps = c.sessions[-1].steps
    assert all("hypothesis" in s and "usage" in s for s in steps)


def test_cost_budget_stops_game():
    m = {"id": "mock", "display_name": "mock", "provider": "mock", "api_model": "mock", "input_modes": ["text"],
         "price_in": 1000.0, "price_out": 1000.0}
    r = play_model(MockClient(), GID, MockProvider(m), m, effort=None, run_key=None,
                   budgets=Budgets(max_cost_usd=5.0))
    assert r.reason == "budget_cost" and r.actions < 10


def test_run_key_stable():
    assert run_key("dev", "g", "m", "low", "h1", 0) == run_key("dev", "g", "m", "low", "h1", 0)
    assert run_key("dev", "g", "m", "low", "h1", 0) != run_key("dev", "g", "m", "low", "h1", 1)


def test_registry_loads_and_unverified_are_unusable():
    ms = load_models()
    assert usable(ms["claude-haiku-5-5"])
    assert not usable(ms["verda-small"])


def test_sweep_resumes(tmp_path):
    from pathlib import Path
    sw = load_sweep(str(Path(__file__).parents[1] / "sweeps" / "mock.yaml"))
    rows = execute(sw, api="mock", dry_run=False, approve_cost=None, out_dir=tmp_path, log=lambda *_: None)
    assert len(rows) == 3 * 2 + 3 * (2 + 1 + 1 + 2)  # model x attempts + baselines
    sw = load_sweep(str(Path(__file__).parents[1] / "sweeps" / "mock.yaml"))
    again = execute(sw, api="mock", dry_run=False, approve_cost=None, out_dir=tmp_path, log=lambda *_: None)
    assert again == []


def test_cost_gate_blocks_expensive_sweep(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-used")
    sw = {"name": "big", "collection": "dev", "games": {"first": 3}, "attempts": 50, "concurrency": 1,
          "models": [{"id": "claude-opus-5-5", "effort": "max"}], "baselines": [], "budgets": {}}
    with pytest.raises(SystemExit):
        execute(sw, api="mock", dry_run=False, approve_cost=None, out_dir=tmp_path, log=lambda *_: None)


def test_models_without_keys_are_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    warnings = []
    sw = {"name": "k", "collection": "dev", "games": {"first": 1}, "attempts": 1, "concurrency": 1,
          "models": [{"id": "claude-haiku-5-5"}], "baselines": [], "budgets": {}}
    rows = execute(sw, api="mock", dry_run=True, approve_cost=None, out_dir=tmp_path, log=warnings.append)
    assert any("no ANTHROPIC_API_KEY" in w for w in warnings)
