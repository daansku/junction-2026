"""Gravity switch: stepping on a switch toggles gravity. While gravity is on, after every
action you fall straight down until something stops you, so you can't climb; a HUD pip is
lit while gravity is on."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "gravity"
DOWN = (0, 1)


def _parse(d):
    return frozenset(tuple(p) for p in d.get("switches", []))


@register
class Gravity(Component):
    name = N
    tier = 3
    layer = 23
    place_order = 57
    roles = {"gravity_switch": (C.LIME, "hbar")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 8:
            return False
        cand = [c for c in path[2:-3] if c not in dr.occupied]
        if not cand:
            return False
        sw = [dr.claim(dr.pick(cand))]
        rest = [c for c in dr.free() if c not in path]
        extra = dr.pick(rest)
        if extra:  # a second switch, so gravity can be turned off again
            sw.append(dr.claim(extra))
        dr.data[N] = {"switches": [list(s) for s in sw]}
        return True

    def init_state(self, level, state):
        state.c[N] = 0

    def on_enter(self, level, state, pos, d, events):
        if pos in static(level, N, _parse):
            state.c[N] ^= 1
            events.append("gravity_on" if state.c[N] else "gravity_off")

    def drift(self, level, state, pos):
        return DOWN if state.c[N] else None

    def draw(self, level, state, cv):
        for p in static(level, N, _parse):
            cv.cell(p, "gravity_switch")

    def hud(self, level, state):
        return [("gravity_switch", state.c[N], 1)]
