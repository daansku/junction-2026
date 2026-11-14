"""A7 forced-interaction generator (`gridforce` family). Frozen `gridworld` collections must
regenerate byte-identically; `gridforce` levels must force their new rule."""
import json
import math
from pathlib import Path

import pytest

from engine import GameSpec, make_game
from engine.cli import verify_game
from engine.core.level import Level
from engine.generator import interaction as I

COL = Path(__file__).resolve().parents[2] / "data" / "collections"


def _load(name):
    p = COL / f"{name}.json"
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["dev", "eval-v1", "eval-v2", "probe-v1", "eval-v3"])
def test_frozen_collections_regenerate_identically(name):
    col = _load(name)
    bad = [(g["game_id"], e) for g in col["games"] if (e := verify_game(g, regen=True))]
    assert not bad, bad[:3]


def test_train_v1_sample_regenerates_identically():
    games = _load("train-v1")["games"]
    step = max(1, len(games) // 120)
    bad = [(g["game_id"], e) for g in games[::step][:120] if (e := verify_game(g, regen=True))]
    assert not bad, bad[:3]


def test_flag_only_on_force_family():
    assert I.forcing("gridforce") and not I.forcing("gridworld")


def test_rule_kinds_cover_registry():
    from engine import components as comps
    kinds = {r: I.kind(r) for r in comps.tiers() if comps.tiers()[r] > 0}
    assert {r for r, k in kinds.items() if k == "constraint"} <= {"no_reverse"}, kinds


def test_avoid_solver_finds_plain_path_and_blocks_cells():
    lv = Level(w=5, h=3, walls=frozenset(), start=(0, 1), goal=(4, 1), rules=("one_way",),
               new_rule="one_way", data={"one_way": {"tiles": [[2, 1, "right"]]}})
    assert I.avoid_optimal(lv, "one_way") == 6           # detour round the tile
    lv2 = Level(w=5, h=1, walls=frozenset(), start=(0, 0), goal=(4, 0), rules=("one_way",),
                new_rule="one_way", data={"one_way": {"tiles": [[2, 0, "right"]]}})
    assert I.avoid_optimal(lv2, "one_way") is math.inf   # corridor: must use it
    assert I.avoid_optimal(lv, "one_way", limit=5) is math.inf


@pytest.mark.parametrize("d,n,seed", [(1, 6, 7101), (2, 6, 7102), (3, 6, 7103), (4, 8, 7104)])
def test_gridforce_forces_new_rule(d, n, seed):
    g = make_game(GameSpec(family="gridforce", seed=seed, difficulty=d, n_levels=n))
    assert g.game_id.startswith(f"gridforce-s{seed}-d{d}-l{n}-")
    assert not verify_game(g.to_dict(), regen=True)       # deterministic, solvable, in budget
    for lv in g.levels:
        assert len(lv.rules) <= I.MAX_RULES[d]
        assert len(I.SCRAMBLERS.intersection(lv.rules)) <= 1
        if lv.new_rule and I.scored(lv.new_rule):
            assert I.rule_forced(lv, lv.new_rule), (g.game_id, lv.new_rule)


def test_gridforce_differs_from_gridworld():
    a = make_game(GameSpec(family="gridworld", seed=7105, difficulty=2))
    b = make_game(GameSpec(family="gridforce", seed=7105, difficulty=2))
    assert a.game_id.split("-")[-1] != b.game_id.split("-")[-1]


def test_eval_v3_forces_every_new_rule():
    col = _load("eval-v3")
    assert all(g["game_id"].startswith("gridforce-s93") for g in col["games"])
    for g in col["games"]:
        for ld in g["levels"]:
            lv = Level.from_dict(ld)
            if lv.new_rule and I.scored(lv.new_rule):
                assert I.rule_forced(lv, lv.new_rule), (g["game_id"], lv.new_rule)
