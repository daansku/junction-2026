"""A1-22 reward functions: pure, deterministic `(sample, model_output) -> float in [0, 1]`.

`sample` is the dict written by `python -m engine tasks` (Sample.to_dict()). The reply may
contain reasoning of any length; only the text after its LAST 'ANSWER:' is graded (single-line
answers: first line only, so trailing prose is ignored). No 'ANSWER:' or an answer over 6,000
characters -> 0.
Partial credit exists only where PLAN-v1 §4.6 defines it (plan efficiency); everything else is
exact match, so a policy cannot farm reward with empty, repeated or hedged answers.
"""
from __future__ import annotations

from ..core.actions import Action, parse_action
from ..core.level import Level
from ..core.step import LEVEL_WON, LOST, initial_state, step_level
from .auxtasks import TASKS
from .common import extract_answer



def reward(sample: dict, output: str) -> float:
    if not output:
        return 0.0
    ans = extract_answer(output)
    if ans is None:
        return 0.0
    grade = TASKS[sample["task"]][1]
    try:
        return float(grade(sample, ans))
    except Exception:  # noqa: BLE001  malformed answers never crash a training run
        return 0.0


def episode_score(level: Level | dict, actions: list[str | Action]) -> float:
    """Single-level multi-turn episode, PLAN-v1 §4.6: min(1, optimal / actions) if the level is
    finished, else 0. RESET restarts the level and counts as an action; after a loss only RESET
    helps. Actions beyond the move budget on one attempt end that attempt (lost)."""
    lv = Level.from_dict(level) if isinstance(level, dict) else level
    s, n, alive = initial_state(lv), 0, True
    for a in actions:
        a = parse_action(a)
        n += 1
        if a == Action.RESET:
            s, alive = initial_state(lv), True
            continue
        if not alive or a not in (Action.ACTION1, Action.ACTION2, Action.ACTION3, Action.ACTION4, Action.ACTION5):
            continue
        s, _, out = step_level(lv, s, a)
        if out == LEVEL_WON:
            return min(1.0, lv.optimal_moves / n)
        if out == LOST or s.moves >= lv.move_budget:
            alive = False
    return 0.0
