"""Ice. Moving onto ice keeps you sliding in the same direction until something blocks you
or you reach a non-ice cell."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "ice"


def _parse(d):
    return frozenset(tuple(p) for p in d.get("cells", []))


@register
class Ice(Component):
    name = N
    tier = 1
    layer = 15
    place_order = 80
    roles = {"ice": (C.AZURE, "diag")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 6:
            return False
        n = 1 if dr.teaching else 1 + dr.difficulty // 2
        ice: set = set()
        for _ in range(n):
            cx, cy = dr.rng.choice(path[2:-2])
            rw, rh = dr.rng.randint(2, 4), dr.rng.randint(2, 4)
            x0, y0 = cx - dr.rng.randint(0, rw - 1), cy - dr.rng.randint(0, rh - 1)
            for y in range(y0, y0 + rh):
                for x in range(x0, x0 + rw):
                    p = (x, y)
                    if dr.inb(p) and p not in dr.walls and p not in dr.occupied:
                        ice.add(p)
        if len(ice) < 3:
            return False
        for p in ice:
            dr.claim(p)
        dr.data[N] = {"cells": [list(p) for p in sorted(ice)]}
        return True

    def slide(self, level, state, pos, d):
        return pos in static(level, N, _parse)

    def draw(self, level, state, cv):
        for p in static(level, N, _parse):
            cv.cell(p, "ice")
