"""ARC-AGI-3 compatible action set (PLAN.md §4.2)."""
from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    RESET = "RESET"
    ACTION1 = "ACTION1"  # up
    ACTION2 = "ACTION2"  # down
    ACTION3 = "ACTION3"  # left
    ACTION4 = "ACTION4"  # right
    ACTION5 = "ACTION5"  # interact (only in games that use it)
    ACTION6 = "ACTION6"  # click x,y (reserved, unused in v1)
    ACTION7 = "ACTION7"  # undo (disabled in v1)

    def __str__(self) -> str:  # json-friendly
        return self.value


DIRS: dict[Action, tuple[int, int]] = {
    Action.ACTION1: (0, -1),
    Action.ACTION2: (0, 1),
    Action.ACTION3: (-1, 0),
    Action.ACTION4: (1, 0),
}
MOVE_ACTIONS: tuple[Action, ...] = tuple(DIRS)

_ALIASES = {
    "UP": Action.ACTION1, "DOWN": Action.ACTION2, "LEFT": Action.ACTION3, "RIGHT": Action.ACTION4,
    "INTERACT": Action.ACTION5, "CLICK": Action.ACTION6, "UNDO": Action.ACTION7,
}


def parse_action(a: "Action | str | int") -> Action:
    """Accept Action, 'ACTION3', 'RESET', 'left', or an int 0..7 (0 = RESET)."""
    if isinstance(a, Action):
        return a
    if isinstance(a, int):
        return Action.RESET if a == 0 else Action(f"ACTION{a}")
    s = str(a).strip().upper()
    if s in _ALIASES:
        return _ALIASES[s]
    return Action(s)
