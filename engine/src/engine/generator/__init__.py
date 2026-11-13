"""Level and game generation: layout -> placement -> solve -> budget -> validity checks.

Every candidate is derived from (seed, family, difficulty, level, attempt) so generation is
fully deterministic; a rejected candidate moves on to the next attempt sub-seed.
"""
from __future__ import annotations

from ..core.actions import Action
from ..core.level import Level
from ..core.rng import rng_for
from ..solver import compute_budget, random_walk_win_rate, solve
from .layout import STYLES, distances, floor_cells, make_layout

SLACK = {1: 3.0, 2: 2.5, 3: 2.0, 4: 1.5}
INTRO_ALLOWANCE = 8           # extra moves on a level that introduces a new rule
MAX_ATTEMPTS = 200
RANDOM_WALK_MAX = 0.02


class GenerationError(RuntimeError):
    pass


def _size(rng, difficulty: int) -> tuple[int, int]:
    lo = 7 + difficulty
    w = rng.randint(lo, min(16, lo + 4))
    h = rng.randint(lo, min(14, lo + 3))
    return w, h


def _min_optimal(difficulty: int, level_idx: int) -> int:
    return 6 + 2 * difficulty + level_idx


def generate_level(seed: int, family: str, difficulty: int, level_idx: int,
                   rules: tuple[str, ...] = (), new_rule: str | None = None) -> Level:
    slack = SLACK.get(difficulty, 2.5)
    for attempt in range(MAX_ATTEMPTS):
        rng = rng_for(family, seed, difficulty, "level", level_idx, attempt)
        w, h = _size(rng, difficulty)
        style = rng.choice(STYLES)
        walls = make_layout(rng, style, w, h, density=0.12 + 0.03 * difficulty)
        cells = floor_cells(w, h, walls)
        if len(cells) < 12:
            continue
        start = rng.choice(cells)
        dist = distances(w, h, walls, start)
        far = sorted((d, p) for p, d in dist.items() if d > 0)
        if not far:
            continue
        cut = far[int(len(far) * 0.7):]  # goal from the farthest 30% of reachable cells
        goal = rng.choice(cut)[1]
        lv = Level(w=w, h=h, walls=frozenset(walls), start=start, goal=goal,
                   rules=tuple(rules), new_rule=new_rule, data={"layout": style})
        path = solve(lv)
        if path is None or len(path) < _min_optimal(difficulty, level_idx):
            continue
        lv.optimal_moves = len(path)
        lv.optimal_path = [a.value for a in path]
        lv.move_budget = compute_budget(len(path), slack, INTRO_ALLOWANCE if new_rule else 0)
        if random_walk_win_rate(lv, tries=200, seed=(seed, level_idx, attempt)) >= RANDOM_WALK_MAX:
            continue
        lv.data["attempt"] = attempt
        return lv
    raise GenerationError(f"no valid level: seed={seed} d={difficulty} level={level_idx}")


def generate_levels(seed: int, family: str, difficulty: int, n_levels: int,
                    rules: list[str] | None = None) -> list[Level]:
    """Stub curriculum (tier 0 only): every level is walls + goal + budget. The real
    curriculum (one new rule per level, unique combinations) replaces this in A1-08."""
    return [generate_level(seed, family, difficulty, i) for i in range(n_levels)]


__all__ = ["generate_level", "generate_levels", "GenerationError", "Action"]
