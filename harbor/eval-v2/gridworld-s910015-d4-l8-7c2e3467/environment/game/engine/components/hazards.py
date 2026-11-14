"""Hazards + health. Stepping onto a hazard costs one health pip; at zero health the level is
lost. The generator puts a run of hazards on the shortest path, as long as total health, so
walking straight through kills you and a detour is required."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "hazards"


def _parse(d):
    return frozenset(tuple(p) for p in d.get("cells", [])), int(d.get("max_health", 3))


@register
class Hazards(Component):
    name = N
    tier = 1
    layer = 20
    place_order = 60
    roles = {"hazard": (C.MAGENTA, "cross"), "health": ("@player", "full")}

    def place(self, dr):
        hp = 2 if dr.teaching else 3
        path = dr.path()
        if not path or len(path) < hp + 5:
            return False
        lo = dr.rng.randint(2, len(path) - hp - 2)
        seg = path[lo:lo + hp]
        if any(c in dr.occupied for c in seg):
            return False
        cells = [dr.claim(c) for c in seg]
        extra = 0 if dr.teaching else dr.difficulty * 2
        free = dr.free()
        for c in (dr.rng.sample(free, min(extra, len(free))) if free else []):
            cells.append(dr.claim(c))
        dr.data[N] = {"cells": [list(c) for c in cells], "max_health": hp}
        return True

    def init_state(self, level, state):
        state.c[N] = static(level, N, _parse)[1]

    def on_enter(self, level, state, pos, d, events):
        if pos in static(level, N, _parse)[0]:
            state.c[N] -= 1
            events.append("hurt")

    def lost(self, level, state):
        return state.c[N] <= 0

    def draw(self, level, state, cv):
        for p in static(level, N, _parse)[0]:
            cv.cell(p, "hazard")

    def hud(self, level, state):
        return [("health", max(0, state.c[N]), static(level, N, _parse)[1])]
