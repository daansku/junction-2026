"""Mirror twin: a second figure copies every move (mirrored left/right on harder levels).
Walls stop the twin independently, so bumping is how you line the two up. The level is won
only when you stand on the goal while the twin stands on its own goal."""
from __future__ import annotations

from .base import Component, static
from . import register, hooks
from ..core.actions import DIRS, Action
from ..render import colors as C

N = "twin"
MIRROR = {Action.ACTION3: Action.ACTION4, Action.ACTION4: Action.ACTION3}


def _parse(d):
    return tuple(d["start"]), tuple(d["goal"]), bool(d.get("mirror", False))


@register
class Twin(Component):
    name = N
    tier = 2
    layer = 90
    place_order = 85
    roles = {"twin": (C.WHITE, "dot"), "twin_goal": ("@twin", "ring")}

    def place(self, dr):
        free = dr.free()
        if len(free) < 4:
            return False
        reach = dr.reach(dr.start)
        free = [c for c in free if c in reach]
        s = dr.pick_far(free, {dr.start}, 0.5)
        if s is None:
            return False
        dr.claim(s)
        g_cand = [c for c in free if c not in dr.occupied]
        g = dr.pick_far(g_cand, {s}, 0.5)
        if g is None:
            return False
        dr.claim(g)
        mirror = (not dr.teaching) and dr.difficulty >= 2 and dr.rng.random() < 0.6
        dr.data[N] = {"start": list(s), "goal": list(g), "mirror": mirror}
        return True

    def init_state(self, level, state):
        state.c[N] = static(level, N, _parse)[0]

    def on_action(self, level, state, action, events):
        if action not in DIRS:
            return
        _, _, mirror = static(level, N, _parse)
        a = MIRROR.get(action, action) if mirror else action
        dx, dy = DIRS[a]
        x, y = state.c[N]
        t = (x + dx, y + dy)
        if level.in_bounds(t) and not any(c.blocks_object(level, state, t) for c in hooks(level, "blocks_object")):
            state.c[N] = t

    def win_ok(self, level, state):
        return state.c[N] == static(level, N, _parse)[1]

    def draw(self, level, state, cv):
        _, goal, _ = static(level, N, _parse)
        cv.cell(goal, "twin_goal")
        cv.cell(state.c[N], "twin")
