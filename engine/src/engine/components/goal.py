from __future__ import annotations

from .base import Component
from . import register
from ..render import colors as C


@register
class Goal(Component):
    """Standing on the goal wins the level, if every active component's win_ok agrees."""
    name = "goal"
    always_on = True
    layer = 20
    roles = {"goal": (C.GREEN, "ring")}

    def draw(self, level, state, cv):
        cv.cell(level.goal, "goal")
