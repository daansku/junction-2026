"""Level and game generation: layout -> placement -> solve -> budget -> validity checks.

Every candidate is derived from (seed, family, difficulty, level, rules, attempt) so
generation is fully deterministic; a rejected candidate moves on to the next attempt sub-seed.

Validity (PLAN.md §5), checked on every level:
  * solvable (BFS over full state)
  * every active rule matters: removing it changes the optimal length (or makes it unsolvable)
  * budget = ceil(optimal x slack) (+ allowance on levels that introduce a rule)
  * a random walk wins < 2% of 200 tries
"""
from __future__ import annotations

from .. import components as comps
from ..core.level import Level
from ..core.rng import rng_for
from dataclasses import replace

from ..solver import compute_budget, random_walk_win_rate, replay_wins, solve
from . import curriculum
from .layout import STYLES, make_layout
from .placement import Draft

SLACK = {1: 3.0, 2: 2.5, 3: 2.0, 4: 1.5}
INTRO_ALLOWANCE = 8
MAX_ATTEMPTS = 150
ATTEMPTS_PER_CANDIDATE = 60  # when fallback rule sets exist, give up on one set sooner
RANDOM_WALK_MAX = 0.02
SOLVER_CAP = 50_000


class GenerationError(RuntimeError):
    pass


def _size(rng, difficulty: int, teaching: bool) -> tuple[int, int]:
    lo = (6 if teaching else 7) + difficulty
    hi_w, hi_h = (11, 10) if teaching else (16, 14)
    w = rng.randint(lo, min(hi_w, lo + 4))
    h = rng.randint(lo, min(hi_h, lo + 3))
    return w, h


def _min_optimal(difficulty: int, level_idx: int, teaching: bool) -> int:
    return (4 if teaching else 6) + 2 * difficulty + (0 if teaching else level_idx)


def try_level(seed: int, family: str, difficulty: int, level_idx: int, rules: tuple[str, ...],
              new_rule: str | None, attempt: int) -> Level | None:
    """One candidate; None if rejected."""
    teaching = new_rule is not None
    rng = rng_for(family, seed, difficulty, "level", level_idx, ",".join(rules), attempt)
    w, h = _size(rng, difficulty, teaching)
    style = rng.choice(STYLES if not teaching else ("open", "rooms", "rooms", "maze"))
    walls = make_layout(rng, style, w, h, density=0.12 + 0.03 * difficulty)
    floor = [(x, y) for y in range(h) for x in range(w) if (x, y) not in walls]
    if len(floor) < 12:
        return None
    start = rng.choice(floor)
    dr = Draft(w, h, walls, start, start, rng, difficulty, teaching, new_rule)
    dist = dr.reach(start)
    far = sorted((d, p) for p, d in dist.items() if d > 0)
    if not far:
        return None
    dr.goal = rng.choice(far[int(len(far) * 0.7):])[1]
    dr.occupied = {start, dr.goal}
    for c in sorted((comps.REGISTRY[r] for r in rules), key=lambda c: (c.place_order, c.name)):
        if not c.place(dr):
            return None
    data = dict(dr.data)
    data["layout"] = style
    lv = Level(w=w, h=h, walls=frozenset(dr.walls), start=start, goal=dr.goal,
               rules=tuple(rules), new_rule=new_rule, data=data)
    path = solve(lv, max_states=SOLVER_CAP)
    if path is None or len(path) < _min_optimal(difficulty, level_idx, teaching):
        return None
    for r in rules:  # every rule must matter
        if not rule_matters(lv, r, len(path)):
            return None
    lv.optimal_moves = len(path)
    lv.optimal_path = [a.value for a in path]
    lv.move_budget = compute_budget(len(path), SLACK.get(difficulty, 2.5),
                                    INTRO_ALLOWANCE if teaching else 0)
    if random_walk_win_rate(lv, tries=200, seed=(seed, level_idx, attempt)) >= RANDOM_WALK_MAX:
        return None
    lv.data["attempt"] = attempt
    return lv


def rule_matters(lv: Level, rule: str, optimal: int) -> bool:
    """A rule matters if the optimal plan of a player who ignores it is longer, impossible, or
    fails on the real level (PLAN.md §5, strengthened so remap/rotation rules count)."""
    alt = solve(replace(lv, rules=tuple(r for r in lv.rules if r != rule)), max_states=SOLVER_CAP)
    if alt is None or len(alt) != optimal:
        return True
    return not replay_wins(lv, alt)


def generate_level(seed: int, family: str, difficulty: int, level_idx: int,
                   rules: tuple[str, ...] = (), new_rule: str | None = None,
                   max_attempts: int = MAX_ATTEMPTS) -> Level:
    for attempt in range(max_attempts):
        lv = try_level(seed, family, difficulty, level_idx, tuple(rules), new_rule, attempt)
        if lv is not None:
            return lv
    raise GenerationError(f"no valid level: seed={seed} d={difficulty} level={level_idx} rules={rules}")


def generate_levels(seed: int, family: str, difficulty: int, n_levels: int,
                    rules: list[str] | None = None) -> list[Level]:
    levels: list[Level] = []
    used: set[frozenset] = set()
    for i, (primary, new, fallbacks) in enumerate(
            curriculum.plan(seed, family, difficulty, n_levels, rules)):
        lv = None
        for cand in [primary, *fallbacks]:
            if frozenset(cand) in used:
                continue
            try:
                lv = generate_level(seed, family, difficulty, i, cand, new,
                                    ATTEMPTS_PER_CANDIDATE if fallbacks else MAX_ATTEMPTS)
                break
            except GenerationError:
                continue
        if lv is None:  # last resort: teach some unused standalone rule
            taught = {l.new_rule for l in levels}
            for r in curriculum.rule_pool(curriculum.max_tier_for(difficulty)):
                if r in taught or comps.REGISTRY[r].requires or frozenset((r,)) in used:
                    continue
                try:
                    lv = generate_level(seed, family, difficulty, i, (r,), r, ATTEMPTS_PER_CANDIDATE)
                    break
                except GenerationError:
                    continue
        if lv is None:
            raise GenerationError(f"level {i} failed for all rule sets: {[primary, *fallbacks]}")
        used.add(frozenset(lv.rules))
        levels.append(lv)
    return levels


__all__ = ["generate_level", "generate_levels", "try_level", "GenerationError"]
