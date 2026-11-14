"""`game_turn`: RL directly on the maps, in the exact h1 harness turn format.

The prompt is A3's real h1 turn (system prompt, previous NOTES, recent actions with changed-cell
counts, current screen as RLE), reached by playing a train-v1 game from level 1 with the Narrator
writing the notes, plus occasional detours so recovery states appear. The reply is the h1 JSON.

Reward: 1.0 if the reply parses like the harness does (a JSON object, action among the
available ones) AND the action starts a shortest path to finishing the level from this exact
state (BFS over the real engine state, all rules applied); else 0.0. Bumps, detours and
dithering all score 0. After a lost level, only RESET scores.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from functools import lru_cache

from ..core.actions import Action, MOVE_ACTIONS
from ..core.level import Level, State
from ..core.step import LEVEL_WON, LOST, step_level, uses_interact
from .common import Sample, pick_game, task_rng
from .rationale import Narrator

BFS_CAP = 60_000
_JSON = re.compile(r"\{.*\}", re.S)


def optimal_first_actions(level: Level, state: State, cap: int = BFS_CAP) -> tuple[set[str], int] | None:
    """Actions that begin a shortest winning sequence from `state` (budget ignored, like the
    solver), and that shortest length. None if no win is reachable within the cap."""
    lv = replace(level, move_budget=0)
    acts = list(MOVE_ACTIONS) + ([Action.ACTION5] if uses_interact(lv) else [])
    start = state.copy()
    frontier: dict[tuple, tuple[State, set[str]]] = {start.key(): (start, set())}
    seen = {start.key()}
    depth = 0
    while frontier and len(seen) < cap:
        depth += 1
        winners: set[str] = set()
        nxt: dict[tuple, tuple[State, set[str]]] = {}
        for _, (s, first) in frontier.items():
            for a in acts:
                ns, _, out = step_level(lv, s, a)
                f = first or {a.value}
                if out == LEVEL_WON:
                    winners |= f
                    continue
                if out == LOST:
                    continue
                k = ns.key()
                if k in seen and k not in nxt:
                    continue
                if k in nxt:
                    nxt[k][1].update(f)
                else:
                    nxt[k] = (ns, set(f))
        if winners:
            return winners, depth
        seen.update(nxt)
        frontier = nxt
    return None


# ---- A5-21 failure targets: what to oversample ------------------------------------------------
_DEFAULT_MODES = {"zero_change_wall_bump": 0.47, "late_reset": 0.42, "missed_new_rule": 0.06,
                  "premature_hypothesis": 0.05}


@lru_cache(maxsize=1)
def targets() -> dict:
    """A5's `analysis/decision_point_targets.json` (oversample weights from real model failures on
    hold-out-safe runs). Falls back to its 17:55 values if the file is missing."""
    from .common import collections_dir_root
    p = collections_dir_root() / "analysis" / "decision_point_targets.json"
    try:
        w = json.loads(p.read_text(encoding="utf-8"))["oversample_weights"]
        return {"modes": w.get("by_decision_type") or _DEFAULT_MODES, "rules": w.get("by_train_safe_rule") or {}}
    except (OSError, ValueError, KeyError):
        return {"modes": _DEFAULT_MODES, "rules": {}}


def _pick_level(rng, g, rule_w: dict, teaching_only: bool) -> int | None:
    idx = [k for k, lv in enumerate(g.levels) if not teaching_only or lv.new_rule]
    if not idx:
        return None
    w = [1e-3 + (sum(rule_w.get(r, 0.0) for r in g.levels[k].rules) if rule_w else 1.0) for k in idx]
    return rng.choices(idx, weights=w, k=1)[0]


def make_game_turn(seed: int, i: int) -> Sample | None:
    from arena.agent_loop import SYSTEM, build_parts       # A3's harness: train == inference
    from arena.dataset import MODES, parts_to_text

    rng = task_rng("game_turn", seed, i)
    tw = targets()
    modes, mw = zip(*sorted(tw["modes"].items()))
    mode = rng.choices(modes, weights=mw, k=1)[0]
    g = pick_game(rng)
    target = _pick_level(rng, g, tw["rules"], teaching_only=(mode == "missed_new_rule"))
    if target is None:
        return None
    nar = Narrator(g)
    notes, history, turn = "", [], 0
    detour_p = {"zero_change_wall_bump": 0.3, "late_reset": 0.0}.get(mode, 0.1)
    wander_to = None                           # late_reset: wander until this many moves are used
    path: list[str] = []
    for _ in range(1000):
        t = g.truth()
        lvl = t["level"] - 1
        if t["state"] == "WIN" or lvl > target:
            return None
        if lvl < target:                       # earlier levels: play them optimally (fast path)
            if not path:
                path = list(g.level.optimal_path)
            a = path.pop(0)
        else:
            if mode == "late_reset" and wander_to is None:
                lo = max(1, t["move_budget"] - 2 * g.level.optimal_moves)
                wander_to = rng.randint(lo, t["move_budget"])   # == budget -> sample the lost screen
            wandering = wander_to is not None and t["state"] != "GAME_OVER" and t["moves_used"] < wander_to
            if wandering:
                a = rng.choice([m.value for m in MOVE_ACTIONS])
            else:
                if t["state"] == "GAME_OVER":
                    opt: tuple[set[str], int] | None = ({"RESET"}, 0)
                else:
                    opt = optimal_first_actions(g.level, g.state)
                    if opt is None:
                        return None
                    if opt[1] > t["move_budget"] - t["moves_used"]:
                        opt = ({"RESET"}, opt[1])    # can't finish in the moves left: restart now
                if mode == "late_reset" or rng.random() < 0.3 or opt[0] == {"RESET"}:
                    allowed = [x.value for x in g.available_actions()]
                    prompt = parts_to_text(build_parts(g.frame(), notes, history, allowed, MODES, turn + 1))
                    best = sorted(opt[0])[0]
                    n_notes, hyp = nar.before([] if best == "RESET" else [best], None)
                    if best == "RESET" and t["state"] != "GAME_OVER":
                        n_notes += " Not enough moves left to finish this level from here: restart it."
                        hyp = "this attempt cannot finish in the moves left; restarting is cheaper than wandering on"
                    gold = json.dumps({"notes": n_notes, "hypothesis": hyp, "belief": "playing", "action": best})
                    return Sample("game_turn", f"game_turn-{seed}-{i}", prompt, gold,
                                  {"game_id": g.game_id, "level": t["level"], "turn": turn + 1, "mode": mode,
                                   "optimal_actions": sorted(opt[0]), "dist": opt[1], "allowed": allowed,
                                   "state": t["state"], "moves_left": t["move_budget"] - t["moves_used"]},
                                  system=SYSTEM, raw_answer=True)
                if t["state"] == "GAME_OVER":
                    a = "RESET"
                elif rng.random() < detour_p:
                    a = rng.choice([m.value for m in MOVE_ACTIONS])
                else:
                    a = sorted(opt[0])[rng.randrange(len(opt[0]))]
        new_notes, _ = nar.before([] if a == "RESET" else [a], None)
        prev = g.frame()
        g.step(a)
        nar.after(a, g)
        if g.idx != lvl:
            path = []
        turn += 1
        f = g.frame()
        history.append((a, sum(x != y for ra, rb in zip(prev, f) for x, y in zip(ra, rb))))
        notes = new_notes
    return None


def grade_game_turn(s: dict, reply: str) -> float:
    """Harness-identical parse (arena.agent_loop.parse_reply), then: is the action optimal here?"""
    m = _JSON.search(reply or "")
    if not m:
        return 0.0
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return 0.0
    if not isinstance(d, dict):
        return 0.0
    act = str(d.get("action", "")).strip().upper()
    if act not in s["meta"]["allowed"]:
        return 0.0
    return 1.0 if act in s["meta"]["optimal_actions"] else 0.0
