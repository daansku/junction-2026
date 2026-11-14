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
    req = REGISTRY[rule].requires
    rules = tuple(sorted({rule, req[0]})) if req else (rule,)
    lv = generate_level(7, "gridworld", difficulty, 1, rules, rule)
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


# ---- from rules/proposals ------------------------------------------------------
def test_cracked_floor_collapses_behind_you():
    lv = corridor(5, ["cracked_floor"], {"cracked_floor": {"cells": [[2, 1]]}}, rows=1)
    s, _, ev = run(lv, [R, R])
    assert "floor_collapsed" in ev and (2, 1) in s.c["cracked_floor"]
    s2, ev2, _ = step_level(lv, s, L)
    assert s2.pos == (3, 1) and "bump" in ev2


def test_beacon_decoy_sends_home():
    lv = corridor(6, ["beacon_goal"], {"beacon_goal": {"decoys": [[3, 1]]}}, rows=1)
    s, out, ev = run(lv, [R, R])
    assert "decoy" in ev and s.pos == lv.start and out == PLAYING


def test_cracked_floor_needs_partner_in_curriculum():
    from engine.generator.curriculum import plan
    for seed in range(30):
        seen = set()
        for rules, new, _ in plan(seed, "gridworld", 3, 8):
            if new == "cracked_floor":
                assert set(rules) & {"collect_all", "keys_doors", "plates_gates"}
                assert seen & {"collect_all", "keys_doors", "plates_gates"}
            if new:
                seen.add(new)


def test_skin_shuffle_shapes_and_colours_distinct():
    from engine.generator.skin import FIXED, FIXED_SHAPE, make_skin
    rules = ["keys_doors", "hazards", "ice", "push_blocks", "collect_all"]
    a = make_skin(1, "gridworld", True, rules)
    b = make_skin(2, "gridworld", True, rules)
    assert a != b
    for sk in (a, b):
        movable = [r for r in sk if r not in FIXED and r not in FIXED_SHAPE]
        assert len({sk[r][1] for r in movable}) == len(movable)
    assert make_skin(1, "gridworld", True, rules) == a


# ---- tier 3 (opt-in via rules=, not in the default curriculum pool) ----------------
def test_conveyor_carries():
    lv = corridor(7, ["conveyors"], {"conveyors": {"belts": [[3, 1, "right"], [4, 1, "right"]]}}, rows=1)
    s, _, ev = run(lv, [R, R])
    assert s.pos == (5, 1) and "drifted:2" in ev


def test_enemy_catches():
    lv = corridor(7, ["enemies"], {"enemies": {"tracks": [[[3, 1], [4, 1], [5, 1]]]}}, rows=1)
    s, out, ev = run(lv, [R, R])        # enemy t0 (3,1) t1 (4,1) t2 (5,1); player (3,1): safe
    assert out == PLAYING
    s, out, ev = run(lv, [R, R, R])     # t3 enemy back at (4,1) = player
    assert out == LOST and "caught" in ev


def test_enemy_swap_catches():
    lv = corridor(6, ["enemies"], {"enemies": {"tracks": [[[2, 1], [3, 1]]]}}, rows=1)
    s, out, _ = run(lv, [R])            # enemy leaves (2,1) as player enters: safe
    assert out == PLAYING
    s, out, ev = run(lv, [R, R])        # player (2,1)->(3,1) while enemy (3,1)->(2,1): swap
    assert out == LOST


def test_gravity_falls():
    lv = corridor(5, ["gravity"], {"gravity": {"switches": [[2, 1]]}}, rows=4)
    s, _, ev = run(lv, [R])
    assert "gravity_on" in ev and s.pos == (2, 4)
    s2, _, _ = step_level(lv, s, U)   # can't climb: falls straight back
    assert s2.pos == (2, 4)


def test_tier3_not_in_default_pool():
    assert not {"conveyors", "enemies", "gravity"} & set(rule_pool(2))
    assert {"conveyors", "enemies", "gravity"} <= set(rule_pool(3))


# ---- eval-v2 unseen rules (tier 3) ----------------------------------------------------
def test_no_reverse_blocks_u_turn():
    lv = corridor(6, ["no_reverse"], {"no_reverse": {}}, start=(3, 1), rows=1)
    s, _, ev = run(lv, [R, L])
    assert s.pos == (4, 1) and "bump" in ev and s.moves == 2
    s, _, _ = run(lv, [L])                  # first move: no last direction, free
    assert s.pos == (2, 1)
    lv2 = corridor(4, ["no_reverse"], {"no_reverse": {}}, start=(2, 2), goal=(4, 3), rows=3)
    s, _, _ = run(lv2, [R, D, L, U])        # turning is fine, only straight back is blocked
    assert s.pos == (2, 2)


def test_checkpoints_in_order():
    data = {"checkpoints": {"cps": [[3, 1], [2, 1]]}}
    lv = corridor(5, ["checkpoints"], data, rows=1)
    _, out, _ = run(lv, [R, R, R, R])        # touches cp#2 first -> nothing counts
    assert out == PLAYING
    # (2,1) entered out of turn -> 0, (3,1) cp1 -> 1, back to (2,1) cp2 -> 2, then the goal
    _, out, ev = run(lv, [R, R, L, R, R, R])
    assert "checkpoint" in ev
    assert out == LEVEL_WON


def test_pit_filled_by_block():
    data = {"push_blocks": {"blocks": [[2, 1]]}, "pits": {"pits": [[3, 1]]}}
    lv = corridor(5, ["pits", "push_blocks"], data, rows=1)
    s, out, ev = run(lv, [R])                # block pushed into pit: fills it
    assert "pit_filled" in ev and s.pos == (2, 1) and not s.c["push_blocks"]
    s, out, _ = run(lv, [R, R, R, R])
    assert out == LEVEL_WON
    lv2 = corridor(5, ["pits", "push_blocks"], {"push_blocks": {"blocks": []}, "pits": {"pits": [[2, 1]]}}, rows=1)
    s, _, ev = run(lv2, [R])
    assert s.pos == (1, 1) and "bump" in ev


@pytest.mark.parametrize("rules", [("collect_all", "no_reverse"), ("checkpoints",), ("pits", "push_blocks")])
def test_unseen_rules_generate(rules):
    from engine import GameSpec, make_game
    g = make_game(GameSpec(seed=3, n_levels=3, difficulty=2, rules=list(rules)))
    assert set(rules) <= set(g.levels[-1].rules)


def test_d4_games_teach_three_unseen_rules():
    from engine import GameSpec, make_game
    from engine.components import tiers
    t = tiers()
    g = make_game(GameSpec(seed=950000, n_levels=8, difficulty=4))
    assert len({r for lv in g.levels for r in lv.rules if t[r] >= 3}) == 3
    assert {"no_reverse", "checkpoints", "pits"} <= set(rule_pool(3)) and not {"no_reverse", "checkpoints", "pits"} & set(rule_pool(2))
