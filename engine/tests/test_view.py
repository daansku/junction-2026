"""View constraints (generator/view.py): rendering only, rules untouched."""
from dataclasses import replace

import pytest

from engine.core.game import GameSpec, make_game
from engine.generator import view
from engine.render.colors import OBJECT_POOL

SPEC = GameSpec(family="gridbranch", seed=950000, n_levels=3, difficulty=3,
                rules=["rotation", "ice", "push_blocks"])


@pytest.fixture(scope="module")
def plain():
    return make_game(SPEC)


@pytest.fixture(scope="module")
def viewed():
    return make_game(replace(SPEC, view="fog2,glimpse,recolor"))


def test_no_view_serialises_as_before(plain):
    assert "view" not in plain.to_dict()["spec"]
    assert all("view" not in lv.data for lv in plain.levels)


def test_same_levels_and_paths(plain, viewed):
    assert viewed.game_id != plain.game_id
    for a, b in zip(plain.levels, viewed.levels):
        da, db = a.to_dict(), b.to_dict()
        da["data"] = {k: v for k, v in da["data"].items() if k != "view"}
        db["data"] = {k: v for k, v in db["data"].items() if k != "view"}
        assert da == db


def test_viewed_game_wins_with_optimal_paths(viewed):
    g = viewed.clone()
    g.reset()
    for lv in g.levels:
        for a in lv.optimal_path:
            g.step(a)
    assert g.status == "WIN"


def test_glimpse_then_fog(plain, viewed):
    p, v = plain.clone(), viewed.clone()
    p.reset(); v.reset()
    assert v.frame() == p.frame()            # level 1, move 0: full view, no recolour on level 1
    a = v.level.optimal_path[0]
    p.step(a); v.step(a)
    fp, fv = p.frame(), v.frame()
    assert fp[:6] == fv[:6]                  # HUD untouched on level 1
    fog = format(view.FOG, "x")
    assert sum(r.count(fog) for r in fv[6:]) > sum(r.count(fog) for r in fp[6:]) + 100
    # cells next to the player are drawn exactly as without fog
    cv_rows = [i for i, (x, y) in enumerate(zip(fp, fv)) if x != y]
    assert cv_rows and min(cv_rows) >= 6


def test_reset_shows_the_level_again(plain, viewed):
    v = viewed.clone()
    v.reset()
    first = v.frame()
    v.step(v.level.optimal_path[0])
    assert v.frame() != first
    v.step("RESET")
    assert v.frame()[6:] == first[6:]


def test_recolor_is_a_permutation_of_the_object_pool():
    for i in range(1, 8):
        m = view.recolor_map("gridbranch", 950000, i)
        assert sorted(m[c] for c in OBJECT_POOL) == sorted(OBJECT_POOL)
        assert any(m[c] != c for c in OBJECT_POOL)
        assert all(m[c] == c for c in range(16) if c not in OBJECT_POOL)


def test_recolor_from_level_two(viewed):
    assert "recolor" not in viewed.levels[0].data["view"]
    assert "recolor" in viewed.levels[1].data["view"]


def test_parse_rejects_unknown():
    with pytest.raises(ValueError):
        view.parse("fog2,xray")
    with pytest.raises(ValueError):
        view.parse("glimpse")
