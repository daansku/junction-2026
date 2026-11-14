"""Phase walls: solid for `period` actions, open for `period` actions, repeating. Every
counted action advances the clock (bumps too), so you can wait by bumping or pacing."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "phase_walls"


def _parse(d):
    cells = frozenset(tuple(p) for p in d.get("cells", []))
    return cells, int(d.get("period", 3)), int(d.get("phase", 0))


@register
class PhaseWalls(Component):
    name = N
    tier = 2
    layer = 12
    place_order = 50
    roles = {"phase_wall": (C.TEAL, "full"), "phase_open": ("@phase_wall", "corners")}

    def place(self, dr):
        cps = dr.chokepoints()
        if not cps:
            return False
        n = 1 if dr.teaching else min(len(cps), 1 + dr.difficulty // 2)
        cells = [dr.claim(c) for c in dr.rng.sample(cps, n)]
        period = dr.rng.randint(3, 5)
        dr.data[N] = {"cells": [list(c) for c in cells], "period": period,
                      "phase": dr.rng.randrange(2 * period)}
        return True

    def init_state(self, level, state):
        _, period, phase = static(level, N, _parse)
        state.c[N] = phase % (2 * period)

    def _solid(self, level, state, pos):
        cells, period, _ = static(level, N, _parse)
        return pos in cells and state.c[N] < period

    def blocks(self, level, state, pos, d):
        return self._solid(level, state, pos)

    def blocks_object(self, level, state, pos):
        return self._solid(level, state, pos)

    def on_step(self, level, state, events):
        _, period, _ = static(level, N, _parse)
        t = (state.c[N] + 1) % (2 * period)
        if (t < period) != (state.c[N] < period):
            events.append("walls_closed" if t < period else "walls_opened")
        state.c[N] = t

    def draw(self, level, state, cv):
        cells, period, _ = static(level, N, _parse)
        role = "phase_wall" if state.c[N] < period else "phase_open"
        for p in cells:
            cv.cell(p, role)
