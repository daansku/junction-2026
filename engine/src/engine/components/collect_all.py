"""Collect all gems before the goal counts. Gems collected show as HUD pips."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "collect_all"


def _parse(d):
    return frozenset(tuple(p) for p in d.get("gems", []))


@register
class CollectAll(Component):
    name = N
    tier = 2
    layer = 30
    place_order = 75
    roles = {"gem": (C.LIME, "diamond")}

    def place(self, dr):
        path = dr.path()
        if not path:
            return False
        n = 2 if dr.teaching else 2 + dr.difficulty // 2
        reach = dr.reach(dr.start)
        cand = sorted(c for c in reach if c not in dr.occupied)
        gems = []
        for _ in range(n):
            g = dr.pick_far(cand, set(path) | set(gems), 0.3)
            if g is None:
                return False
            gems.append(dr.claim(g))
            cand.remove(g)
        dr.data[N] = {"gems": [list(g) for g in gems]}
        return True

    def init_state(self, level, state):
        state.c[N] = frozenset()

    def on_enter(self, level, state, pos, d, events):
        if pos in static(level, N, _parse) and pos not in state.c[N]:
            state.c[N] = state.c[N] | {pos}
            events.append("collected")

    def win_ok(self, level, state):
        return len(state.c[N]) == len(static(level, N, _parse))

    def draw(self, level, state, cv):
        for g in static(level, N, _parse) - state.c[N]:
            cv.cell(g, "gem")

    def hud(self, level, state):
        return [("gem", len(state.c[N]), len(static(level, N, _parse)))]
