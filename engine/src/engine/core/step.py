"""Pure level transition: (level, state, action) -> (new state, events, outcome).

Used by the Game loop and by the solver, so game rules live in exactly one place.
"""
from __future__ import annotations

from .actions import DIRS, Action
from .level import Level, State
from .. import components as comps

PLAYING, LEVEL_WON, LOST = "PLAYING", "LEVEL_WON", "LOST"
MAX_SLIDE = 64


def initial_state(level: Level) -> State:
    s = State(level.start, 0, {})
    for c in comps.active(level):
        c.init_state(level, s)
    return s


def uses_interact(level: Level) -> bool:
    return any(c.uses_interact for c in comps.active(level))


def _try_move(level: Level, s: State, d: tuple[int, int], active, events: list[str]) -> bool:
    target = (s.pos[0] + d[0], s.pos[1] + d[1])
    if not level.in_bounds(target):
        return False
    if any(c.blocks(level, s, target, d) for c in active):
        return False
    for c in active:
        r = c.push(level, s, target, d, events)
        if r is False:
            return False
    s.pos = target
    for c in active:
        c.on_enter(level, s, target, d, events)
    return True


def step_level(level: Level, state: State, action: Action) -> tuple[State, list[str], str]:
    """Apply one counted action. Caller handles RESET and ignores unavailable actions."""
    active = comps.active(level)
    s = state.copy()
    events: list[str] = []
    for c in active:
        action = c.remap(level, s, action)

    if action in DIRS:
        d = DIRS[action]
        if _try_move(level, s, d, active, events):
            n = 0
            while n < MAX_SLIDE and any(c.slide(level, s, s.pos, d) for c in active):
                if not _try_move(level, s, d, active, events):
                    break
                n += 1
            if n:
                events.append(f"slid:{n}")
        else:
            events.append("bump")
    elif action == Action.ACTION5:
        for c in active:
            c.interact(level, s, events)

    s.moves += 1
    for c in active:
        c.on_step(level, s, events)

    if s.pos == level.goal and all(c.win_ok(level, s) for c in active):
        return s, events, LEVEL_WON
    if any(c.lost(level, s) for c in active):
        return s, events, LOST
    return s, events, PLAYING
