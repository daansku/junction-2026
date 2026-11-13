import json
import random

import pytest

from arena.agent_loop import parse_reply
from arena.dataset import build, game_examples, parts_to_text
from arena.engine_adapter import load_engine
from arena.frames import from_rle, to_rle
from arena.mock_game import MockGame
from arena.providers.openai_compat import OpenAICompatProvider
from arena.solver import solve_level


def engines():
    """Mock always; A2's fake engine / A1's engine when present in the repo."""
    out = [("mock", lambda s: MockGame(s, 3))]
    eng, name = load_engine()
    if name != "arena.mock_game":
        out.append((name, lambda s: eng.make_game(eng.GameSpec(seed=s, n_levels=3))))
    return out


@pytest.mark.parametrize("seed", range(5))
def test_rle_roundtrip_and_smaller(seed):
    f = MockGame(seed).reset()
    r = to_rle(f)
    assert from_rle(r) == f
    assert len(r) < len("".join(f)) / 3


@pytest.mark.parametrize("name,make", engines())
def test_solver_finishes_levels(name, make):
    g = make(1)
    while g.truth()["state"] != "WIN":
        p = solve_level(g)
        assert p, f"{name}: no path at level {g.truth()['level']}"
        for a in p:
            g.step(a)


@pytest.mark.parametrize("name,make", engines())
def test_solver_recovers_from_game_over(name, make):
    g = make(2)
    for _ in range(500):  # bump into things until out of moves
        if g.truth()["state"] == "GAME_OVER":
            break
        g.step("ACTION1")
    if g.truth()["state"] != "GAME_OVER":
        pytest.skip("could not force game over")
    p = solve_level(g)
    assert p and p[0] == "RESET"


@pytest.mark.parametrize("name,make", engines())
@pytest.mark.parametrize("kind", ["optimal", "recover"])
def test_trajectory_targets_win_and_parse(name, make, kind):
    g = make(3)
    exs = game_examples(g, random.Random(0), kind, p_detour=0.3)
    assert g.truth()["state"] == "WIN"
    allowed = ["RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4"]
    for e in exs:
        roles = [m["role"] for m in e["messages"]]
        assert roles == ["system", "user", "assistant"]
        d, err = parse_reply(e["messages"][2]["content"], allowed)
        assert d, err
        u = e["messages"][1]["content"]
        assert "optimal" not in u and "move_budget" not in u  # prompt has no truth fields
    assert exs[-1]["messages"][2]["content"].count('"won"') == 1


def test_optimal_trajectory_is_optimal_length():
    g = MockGame(4, 3)
    opt = sum(lv["optimal_moves"] for lv in g.describe()["levels"])
    exs = game_examples(g, random.Random(0), "optimal")
    assert len(exs) == opt


def test_build_writes_jsonl(tmp_path):
    out = tmp_path / "sft.jsonl"
    stats = build([(f"m{s}", lambda s=s: MockGame(s, 2)) for s in range(3)], out, n_recover=1, log=lambda *_: None)
    lines = out.read_text().splitlines()
    assert len(lines) == stats["optimal"] + stats["recover"] and stats["games"] == 3
    json.loads(lines[0])


def test_train_and_inference_prompts_match():
    """The fine-tuned model must see at inference exactly the string it was trained on."""
    parts = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    captured = {}

    class FakeCompletions:
        def create(self, **kw):
            captured.update(kw)
            raise RuntimeError("stop")

    p = OpenAICompatProvider.__new__(OpenAICompatProvider)
    p.model = {"api_model": "x", "efforts": []}
    p.client = type("C", (), {"chat": type("Ch", (), {"completions": FakeCompletions()})()})()
    with pytest.raises(RuntimeError):
        p.complete("sys", parts)
    assert captured["messages"][1]["content"] == parts_to_text(parts)


def test_refuses_eval_collection():
    from arena.dataset import games_from
    with pytest.raises(SystemExit):
        list(games_from(None, "eval-v1", None))
