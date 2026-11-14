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


def _try_move(level: Level, s: State, d: tuple[int, int], events: list[str]) -> bool:
    target = (s.pos[0] + d[0], s.pos[1] + d[1])
    if not level.in_bounds(target):
        return False
    for c in comps.hooks(level, "blocks"):
        if c.blocks(level, s, target, d):
            return False
    for c in comps.hooks(level, "push"):
        if c.push(level, s, target, d, events) is False:
            return False
    s.pos = target
    for c in comps.hooks(level, "on_enter"):
        c.on_enter(level, s, target, d, events)
    return True


def step_level(level: Level, state: State, action: Action) -> tuple[State, list[str], str]:
    """Apply one counted action. Caller handles RESET and ignores unavailable actions."""
    H = comps.hooks
    s = state.copy()
    events: list[str] = []
    for c in H(level, "remap"):
        action = c.remap(level, s, action)
    for c in H(level, "on_action"):
        c.on_action(level, s, action, events)

    if action in DIRS:
        d = DIRS[action]
        if _try_move(level, s, d, events):
            n = 0
            sliders = H(level, "slide")
            while n < MAX_SLIDE and any(c.slide(level, s, s.pos, d) for c in sliders):
                if not _try_move(level, s, d, events):
                    break
                n += 1
            if n:
                events.append(f"slid:{n}")
        else:
            events.append("bump")
    elif action == Action.ACTION5:
        for c in H(level, "interact"):
            c.interact(level, s, events)

    s.moves += 1
    for c in H(level, "on_step"):
        c.on_step(level, s, events)

    if s.pos == level.goal and all(c.win_ok(level, s) for c in H(level, "win_ok")):
        return s, events, LEVEL_WON
    if any(c.lost(level, s) for c in H(level, "lost")):
        return s, events, LOST
    return s, events, PLAYING
