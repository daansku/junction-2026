"""A1-20..23: training-data tasks, reward functions, rationales, transfer probe."""
import json
from pathlib import Path

import pytest

from engine import components as comps
from engine import splits
from engine.core.game import Game
from engine.tasks import TASKS, episode_score, generate, reward
from engine.tasks.auxtasks import parse_plan
from engine.tasks.common import _games, apply_rle_patch, to_rle
from engine.tasks.rationale import Narrator

COL = Path(__file__).resolve().parents[2] / "data" / "collections"
pytestmark = pytest.mark.skipif(not (COL / "train-v1.json").exists(), reason="train-v1 not built")


def _gold(d):
    return "ANSWER:\n" + d["answer"] if "\n" in d["answer"] else "ANSWER: " + d["answer"]


@pytest.mark.parametrize("task", list(TASKS))
def test_deterministic_and_gold_scores_one(task):
    a = [s.to_dict() for s in generate(task, 15, seed=3)]
    b = [s.to_dict() for s in generate(task, 15, seed=3)]
    assert a == b
    assert all(reward(d, _gold(d)) == 1.0 for d in a)
    assert all(reward(d, "some reasoning first\n" + _gold(d)) == 1.0 for d in a)


@pytest.mark.parametrize("task", list(TASKS))
def test_obvious_exploits_score_zero(task):
    for d in (s.to_dict() for s in generate(task, 15, seed=4)):
        assert reward(d, "") == 0.0
        assert reward(d, d["answer"]) == 0.0                     # no ANSWER: line
        assert reward(d, "ANSWER:") == 0.0                       # empty answer
        assert reward(d, "ANSWER: A B C D") == 0.0               # hedging
        assert reward(d, "x" * 30_000 + _gold(d)) == 0.0         # absurdly long reply
        assert reward(d, "ANSWER: " + "ACTION1 " * 500) == 0.0   # spam


def test_full_plan_efficiency_and_padding():
    for d in (s.to_dict() for s in generate("full_plan", 10, seed=5)):
        opt = d["meta"]["optimal_moves"]
        gold = parse_plan(d["answer"])
        assert len(gold) == opt
        padded = " ".join(a.value for a in gold) + " ACTION1 ACTION2"
        assert reward(d, "ANSWER: " + padded) == pytest.approx(opt / (opt + 2))   # padding costs
        assert reward(d, "ANSWER: " + " ".join(a.value for a in gold[:-1])) == 0.0  # one short fails


def test_next_frame_patch_roundtrip():
    d = next(generate("next_frame", 1, seed=6)).to_dict()
    assert apply_rle_patch(d["meta"]["frame_before"], d["answer"]) == d["meta"]["frame_after"]
    assert apply_rle_patch(d["meta"]["frame_before"], to_rle(d["meta"]["frame_after"])) == d["meta"]["frame_after"]
    assert reward(d, "ANSWER:\n" + to_rle(d["meta"]["frame_after"])) == 1.0  # full frame also accepted
    assert reward(d, "ANSWER:\nr0: 0x10") == 0.0                           # malformed width


def test_sources_are_train_clean():
    tiers = comps.tiers()
    for g in _games("train-v1"):
        assert splits.is_train_ok(g)
        assert lo_ok(g["spec"]["seed"])
        assert all(tiers[r] < 3 for lv in g["levels"] for r in lv["rules"])
    with pytest.raises(ValueError):
        _games("eval-v1")


def lo_ok(seed):
    lo, hi = splits.holdout_doc()["seed_ranges"]["train"]
    return lo <= seed <= hi


def test_episode_score_reset_and_budget():
    d = next(generate("full_plan", 1, seed=7)).to_dict()
    lv, path = d["meta"]["level_data"], parse_plan(d["answer"])
    opt = len(path)
    assert episode_score(lv, path) == 1.0
    assert episode_score(lv, ["ACTION1", "RESET"] + [a.value for a in path]) == pytest.approx(opt / (opt + 2))
    assert episode_score(lv, []) == 0.0
    assert episode_score(lv, ["ACTION5"] * 3) == 0.0


def test_rationales_never_name_rules():
    names = set(comps.REGISTRY) | {n.replace("_", " ") for n in comps.REGISTRY}
    names -= {"goal", "walls", "budget"}
    for raw in _games("train-v1")[:25]:
        g = Game.from_dict(raw)
        nar = Narrator(g)
        for li, lv in enumerate(g.levels):
            for k, a in enumerate(lv.optimal_path):
                notes, hyp = nar.before(list(lv.optimal_path[k:]))
                text = (notes + " " + hyp).lower()
                assert not any(n in text for n in names), (n for n in names if n in text)
                g.step(a)
                nar.after(a, g)


def test_rationale_states_effect_only_after_seeing_it():
    for raw in _games("train-v1")[:60]:
        g = Game.from_dict(raw)
        lv_idx = next((i for i, lv in enumerate(g.levels) if "teleporters" in lv.rules), None)
        if lv_idx is None:
            continue
        g.goto_level(lv_idx + 1)
        nar = Narrator(g)
        notes, _ = nar.before([])
        assert "moves me to the other" not in notes
        for a in g.level.optimal_path:
            g.step(a)
            nar.after(a, g)
            if "teleport" in g.events:
                assert "moves me to the other" in nar.before([])[0]
                return
    pytest.skip("no teleport seen")


def test_probe_levels_are_novel():
    p = COL / "probe-v1.json"
    if not p.exists():
        pytest.skip("probe-v1 not built")
    probe = json.loads(p.read_text(encoding="utf-8"))
    seen = {frozenset(lv["rules"]) for c in ("train-v1", "eval-v1")
            for g in json.loads((COL / f"{c}.json").read_text(encoding="utf-8"))["games"] for lv in g["levels"]}
    tiers = comps.tiers()
    assert probe["split"] == "test" and len(probe["games"]) == 30
    for g in probe["games"]:
        assert g["probe_levels"]
        assert 980000 <= g["spec"]["seed"] < 990000
        for n in g["probe_levels"]:
            assert frozenset(g["levels"][n - 1]["rules"]) not in seen
        assert all(tiers[r] < 3 for lv in g["levels"] for r in lv["rules"])
