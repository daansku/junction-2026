"""Rotation trigger: stepping onto it turns the whole map a quarter turn clockwise on screen.
Controls stay screen-relative (up is always up on screen), so the route you planned before
the turn no longer works. The renderer reads state.c["rotation"]."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..core.actions import DIRS
from ..render import colors as C

N = "rotation"
_BY_VEC = {v: a for a, v in DIRS.items()}


def _parse(d):
    return frozenset(tuple(p) for p in d.get("triggers", []))


def _ccw(v, k):
    dx, dy = v
    for _ in range(k % 4):
        dx, dy = dy, -dx
    return dx, dy


@register
class Rotation(Component):
    name = N
    tier = 2
    layer = 22
    place_order = 55
    roles = {"rotator": (C.WHITE, "tri")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 8:
            return False
        cps = [c for c in dr.chokepoints() if path.index(c) < len(path) - 3]
        on_path = [c for c in path[2:-3] if c not in dr.occupied]
        cand = cps or on_path
        if not cand:
            return False
        trig = [dr.claim(dr.pick(cand))]
        if not dr.teaching and dr.difficulty >= 2:
            rest = [c for c in dr.free() if c not in path]
            extra = dr.pick(rest)
            if extra:
                trig.append(dr.claim(extra))
        dr.data[N] = {"triggers": [list(t) for t in trig]}
        return True

    def init_state(self, level, state):
        state.c[N] = 0

    def remap(self, level, state, action):
        k = state.c[N]
        if k and action in DIRS:
            return _BY_VEC[_ccw(DIRS[action], k)]
        return action

    def on_enter(self, level, state, pos, d, events):
        if pos in static(level, N, _parse):
            state.c[N] = (state.c[N] + 1) % 4
            events.append("rotated")

    def draw(self, level, state, cv):
        for p in static(level, N, _parse):
            cv.cell(p, "rotator")
