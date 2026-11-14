"""No U-turns: you can't move straight back the way you just came. A move opposite to your
last step is a bump (it still costs the action). The cell you just left is marked. Only
matters when the route has to come back out of a dead end, so it is always taught together
with a rule that forces a detour (collect_all, keys_doors or plates_gates)."""
from __future__ import annotations

from .base import Component
from . import register
from ..core.actions import DIRS
from ..render import colors as C

N = "no_reverse"


@register
class NoReverse(Component):
    name = N
    tier = 3
    layer = 12
    place_order = 96
    requires = ("collect_all", "keys_doors", "plates_gates")
    roles = {"trail": (C.VIOLET, "dot")}

    def place(self, dr):
        dr.data[N] = {}
        return True

    def init_state(self, level, state):
        state.c[N] = (None, None)  # (last direct move direction, direction being attempted)

    def on_action(self, level, state, action, events):
        last, _ = state.c[N]
        state.c[N] = (last, DIRS.get(action))

    def blocks(self, level, state, pos, d):
        last, pend = state.c[N]
        return (pend is not None and d == pend and last is not None
                and d == (-last[0], -last[1]))

    def on_enter(self, level, state, pos, d, events):
        last, pend = state.c[N]
        if pend is not None and d == pend:  # the direct move, not a slide/drift/teleport
            state.c[N] = (d, None)

    def on_step(self, level, state, events):
        state.c[N] = (state.c[N][0], None)

    def draw(self, level, state, cv):
        last = state.c[N][0]
        if last is not None:
            back = (state.pos[0] - last[0], state.pos[1] - last[1])
            if level.in_bounds(back) and back not in level.walls:
                cv.cell(back, "trail")
