"""Level solver and validity checks (PLAN.md §5)."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import replace

from ..core.actions import MOVE_ACTIONS, Action
from ..core.level import Level
from ..core.rng import rng_for
from ..core.step import LEVEL_WON, LOST, initial_state, step_level, uses_interact

DEFAULT_MAX_STATES = 300_000
STATS = {"states": 0}  # cumulative states expanded; the generator uses it as a work budget


def solve(level: Level, max_states: int = DEFAULT_MAX_STATES) -> list[Action] | None:
    """Shortest action sequence that wins the level, ignoring the move budget. None if
    unsolvable (or state cap hit -> treated as unsolvable, the generator retries)."""
    lv = replace(level, move_budget=0)
    actions = list(MOVE_ACTIONS) + ([Action.ACTION5] if uses_interact(lv) else [])
    s0 = initial_state(lv)
    parent: dict[tuple, tuple[tuple, Action] | None] = {s0.key(): None}
    q = deque([s0])
    while q:
        s = q.popleft()
        for a in actions:
            ns, _, out = step_level(lv, s, a)
            if out == LOST:
                continue
            k = ns.key()
            if out == LEVEL_WON:
                path = [a]
                cur = s.key()
                while parent[cur] is not None:
                    cur, pa = parent[cur]
                    path.append(pa)
                return path[::-1]
            if k in parent:
                continue
            parent[k] = (s.key(), a)
            STATS["states"] += 1
            if len(parent) > max_states:
                return None
            q.append(ns)
    return None


def compute_budget(optimal: int, slack: float, allowance: int = 0) -> int:
    return math.ceil(optimal * slack) + allowance


def random_walk_win_rate(level: Level, tries: int = 200, seed: object = 0) -> float:
    """Fraction of uniform-random walks that win within the level's budget."""
    rng = rng_for("random-walk", seed)
    actions = list(MOVE_ACTIONS) + ([Action.ACTION5] if uses_interact(level) else [])
    budget = level.move_budget or 200
    wins = 0
    for _ in range(tries):
        s = initial_state(level)
        for _ in range(budget):
            s, _, out = step_level(level, s, rng.choice(actions))
            if out == LEVEL_WON:
                wins += 1
                break
            if out == LOST:
                break
    return wins / tries


def replay_wins(level: Level, path: list[Action | str]) -> bool:
    """Check that a path wins the level within its budget."""
    from ..core.actions import parse_action
    s = initial_state(level)
    for a in path:
        s, _, out = step_level(level, s, parse_action(a))
        if out == LEVEL_WON:
            return True
        if out == LOST:
            return False
    return False


def neutralised_optimal(level: Level, rule: str) -> int | None:
    """Optimal length with `rule` removed — used for the 'new rule must matter' check."""
    lv = replace(level, rules=tuple(r for r in level.rules if r != rule))
    p = solve(lv)
    return None if p is None else len(p)
