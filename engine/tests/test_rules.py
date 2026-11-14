"""Behaviour of each tier-1 rule on tiny hand-built levels, plus generation for each rule."""
import pytest

from engine.components import REGISTRY
from engine.core.actions import Action
from engine.core.level import Level
from engine.core.step import LEVEL_WON, LOST, PLAYING, initial_state, step_level
from engine.generator import generate_level, rule_matters
from engine.generator.curriculum import rule_pool
from engine.solver import neutralised_optimal, solve

U, D, L, R, I = Action.ACTION1, Action.ACTION2, Action.ACTION3, Action.ACTION4, Action.ACTION5


def corridor(n, rules, data, start=(1, 1), goal=None, rows=3):
    """Walled box `n` wide, `rows` tall; open interior."""
    w, h = n + 2, rows + 2
    walls = frozenset((x, y) for y in range(h) for x in range(w) if x in (0, w - 1) or y in (0, h - 1))
    return Level(w=w, h=h, walls=walls, start=start, goal=goal or (n, 1), rules=tuple(rules), data=data)


def run(level, actions):
    s = initial_state(level)
    out, events = PLAYING, []
    for a in actions:
        s, ev, out = step_level(level, s, a)
        events += ev
        if out != PLAYING:
            break
    return s, out, events


def test_keys_doors():
    lv = corridor(6, ["keys_doors"], {"keys_doors": {"keys": [[2, 2]], "doors": [[4, 1]]}}, rows=2)
    s, out, ev = run(lv, [R, R, R])         # walk into the door without a key -> bump
    assert s.pos == (3, 1) and "bump" in ev
    s, out, ev = run(lv, [R, D, R, U, R, R, R])  # key at (2,2), then through the door
    assert "picked_key" in ev and "opened_door" in ev and out == LEVEL_WON


def test_plates_gates_toggle():
    lv = corridor(6, ["plates_gates"], {"plates_gates": {"plates": [[2, 2]], "gates": [[4, 1, 0]]}}, rows=2)
    s, out, ev = run(lv, [R, R, R])
    assert s.pos == (3, 1)
    s, out, ev = run(lv, [R, D, U, R, R, R, R])
    assert "pressed_plate" in ev and out == LEVEL_WON
    # stepping on the plate twice closes it again
    s, out, ev = run(lv, [R, D, U, D, U, R, R, R])
    assert s.pos == (3, 1) and out == PLAYING


def test_teleporters():
    lv = corridor(6, ["teleporters"], {"teleporters": {"pairs": [[2, 1, 5, 3]]}})
    lv = Level(**{**lv.__dict__, "walls": lv.walls | {(4, 1), (4, 2), (4, 3)}})
    lv.__dict__.pop("_cache", None)
    s, out, ev = run(lv, [R])
    assert s.pos == (5, 3) and "teleport" in ev
    assert run(lv, [R, U, U, R])[1] == LEVEL_WON


def test_hazards_damage_and_death():
    lv = corridor(6, ["hazards"], {"hazards": {"cells": [[2, 1], [3, 1]], "max_health": 2}})
    s, out, ev = run(lv, [R])
    assert s.c["hazards"] == 1 and "hurt" in ev
    s, out, ev = run(lv, [R, R])
    assert out == LOST


def test_push_blocks():
    lv = corridor(6, ["push_blocks"], {"push_blocks": {"blocks": [[3, 1]]}}, rows=1)
    s, out, ev = run(lv, [R, R])
    assert s.pos == (3, 1) and (4, 1) in s.c["push_blocks"] and "pushed" in ev
    s, out, ev = run(lv, [R, R, R, R, R])   # block can't enter the goal -> stuck
    assert s.pos == (4, 1) and out == PLAYING


def test_one_way():
    lv = corridor(6, ["one_way"], {"one_way": {"tiles": [[3, 1, "left"]]}}, rows=1)
    s, out, ev = run(lv, [R, R])
    assert s.pos == (2, 1) and "bump" in ev
    lv2 = corridor(6, ["one_way"], {"one_way": {"tiles": [[3, 1, "right"]]}}, rows=1)
    assert run(lv2, [R] * 5)[1] == LEVEL_WON


def test_ice_slides_until_blocked():
    lv = corridor(8, ["ice"], {"ice": {"cells": [[2, 1], [3, 1], [4, 1]]}}, goal=(8, 3))
    s, out, ev = run(lv, [R])
    assert s.pos == (5, 1) and "slid:3" in ev


def test_tier1_all_registered():
    assert {"keys_doors", "plates_gates", "teleporters", "hazards", "push_blocks", "one_way",
            "ice"} <= set(REGISTRY)


@pytest.mark.parametrize("rule", rule_pool(2))
@pytest.mark.parametrize("difficulty", [1, 3])
def test_generated_teaching_level(rule, difficulty):
    lv = generate_level(7, "gridworld", difficulty, 1, (rule,), rule)
    path = solve(lv)
    assert path is not None and len(path) == lv.optimal_moves <= lv.move_budget
    assert rule_matters(lv, rule, lv.optimal_moves)


# ---- tier 2 -------------------------------------------------------------------
def test_collect_all_gates_goal():
    lv = corridor(5, ["collect_all"], {"collect_all": {"gems": [[2, 2]]}}, rows=2)
    assert run(lv, [R] * 4)[1] == PLAYING             # goal ignored without the gem
    s, out, ev = run(lv, [R, D, U, R, R, R])
    assert "collected" in ev and out == LEVEL_WON


def test_phase_walls_cycle():
    lv = corridor(5, ["phase_walls"], {"phase_walls": {"cells": [[3, 1]], "period": 2, "phase": 0}}, rows=1)
    s, out, ev = run(lv, [R, R])        # t=1 at second move: still solid -> bump
    assert s.pos == (2, 1) and "bump" in ev
    s, out, ev = run(lv, [R, L, R, R])  # t=3 open
    assert s.pos == (3, 1)


def test_rotation_turns_controls():
    lv = corridor(6, ["rotation"], {"rotation": {"triggers": [[2, 2]]}}, rows=3)
    s, _, ev = run(lv, [R, D])          # land on trigger
    assert "rotated" in ev and s.c["rotation"] == 1
    s2, _, _ = step_level(lv, s, U)     # screen-up after one cw turn = logical left
    assert s2.pos == (1, 2)


def test_rotation_render_changes_frame():
    from engine.core.game import Game, GameSpec
    from engine.generator.skin import make_skin
    lv = corridor(6, ["rotation"], {"rotation": {"triggers": [[2, 1]]}}, rows=2)
    g = Game(GameSpec(), [lv], make_skin(0, "gridworld", False, ["rotation"]))
    f0 = g.frame()
    g.step(R)
    assert "rotated" in g.events and g.frame() != f0


def test_remap_mirror():
    lv = corridor(6, ["remap"], {"remap": {"triggers": [[2, 1]], "mode": "mirror_h"}}, rows=1)
    s, _, ev = run(lv, [R, R])          # 2nd R is mirrored to L after the trigger
    assert "controls_changed" in ev and s.pos == (1, 1)


def test_twin_must_reach_its_goal():
    lv = corridor(5, ["twin"], {"twin": {"start": [1, 3], "goal": [4, 3], "mirror": False}}, rows=3)
    s, out, ev = run(lv, [R, R, R])
    assert s.c["twin"] == (4, 3) and out == PLAYING   # player at (4,1), goal is (5,1)
    assert run(lv, [R, R, R, R])[1] == PLAYING          # twin overshoots to (5,3)
    lv2 = corridor(5, ["twin"], {"twin": {"start": [1, 3], "goal": [5, 3], "mirror": False}}, rows=3)
    assert run(lv2, [R] * 4)[1] == LEVEL_WON


def test_twin_mirror():
    lv = corridor(6, ["twin"], {"twin": {"start": [6, 3], "goal": [1, 3], "mirror": True}}, rows=3)
    s, _, _ = run(lv, [R])
    assert s.c["twin"] == (5, 3)


def test_stamina_and_refill():
    lv = corridor(8, ["stamina"], {"stamina": {"refills": [[3, 2]], "max": 3}}, rows=2)
    assert run(lv, [R, R, R])[1] == LOST
    s, out, ev = run(lv, [R, R, D])     # refill on 3rd action
    assert "refilled" in ev and s.c["stamina"][0] == 3


def test_all_tier2_registered():
    assert {"collect_all", "phase_walls", "rotation", "remap", "twin", "stamina"} <= set(REGISTRY)
