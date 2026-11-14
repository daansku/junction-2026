from __future__ import annotations

from .base import Component
from . import register
from ..render import colors as C


@register
class MoveBudget(Component):
    """Level is lost when the move counter reaches the budget without winning.
    The bar itself is drawn by the HUD renderer (top two rows), not here."""
    name = "budget"
    always_on = True
    roles = {"budget_bar": (C.BUDGET_BAR, "full"), "budget_empty": (C.BUDGET_EMPTY, "full")}

    def lost(self, level, state):
        return level.move_budget > 0 and state.moves >= level.move_budget
