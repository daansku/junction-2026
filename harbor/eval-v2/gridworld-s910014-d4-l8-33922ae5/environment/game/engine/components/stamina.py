"""Stamina + refills. Every counted action costs one stamina; at zero the level is lost.
Refill pads restore stamina to full and are used up. Stamina shows as a HUD bar of pips."""
from __future__ import annotations

import math

from .base import Component, static
from . import register
from ..render import colors as C

N = "stamina"


def _parse(d):
    return frozenset(tuple(p) for p in d.get("refills", [])), int(d.get("max", 8))


@register
class Stamina(Component):
    name = N
    tier = 2
    layer = 21
    place_order = 90
    roles = {"refill": (C.AZURE, "dot"), "stamina": ("@refill", "full")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 10:
            return False
        L = len(path) - 1
        mx = max(5, math.ceil(L * dr.rng.uniform(0.45, 0.7)))
        n = 1 if dr.teaching else 1 + dr.difficulty // 2
        reach = dr.reach(dr.start)
        refills = []
        for _ in range(n + (0 if dr.teaching else 1)):  # one decoy off the useful route
            cand = sorted(c for c in reach if c not in dr.occupied and 2 <= reach[c] <= mx - 1)
            r = dr.pick_far(cand, set(path), 0.6)
            if r is None:
                break
            refills.append(dr.claim(r))
        if not refills:
            return False
        dr.data[N] = {"refills": [list(r) for r in refills], "max": min(mx, 16)}
        return True

    def init_state(self, level, state):
        state.c[N] = (static(level, N, _parse)[1], frozenset())

    def on_enter(self, level, state, pos, d, events):
        refills, mx = static(level, N, _parse)
        st, used = state.c[N]
        if pos in refills and pos not in used:
            state.c[N] = (mx + 1, used | {pos})  # +1: this action's cost is paid in on_step
            events.append("refilled")

    def on_step(self, level, state, events):
        st, used = state.c[N]
        state.c[N] = (st - 1, used)

    def lost(self, level, state):
        return state.c[N][0] <= 0

    def draw(self, level, state, cv):
        refills, _ = static(level, N, _parse)
        for r in refills - state.c[N][1]:
            cv.cell(r, "refill")

    def hud(self, level, state):
        return [("stamina", max(0, state.c[N][0]), static(level, N, _parse)[1])]
