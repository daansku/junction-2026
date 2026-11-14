"""Ordered checkpoints: the goal only counts after you have touched every checkpoint in
order. The next checkpoint is drawn solid, later ones hollow. Stepping on a later checkpoint
out of turn wipes your progress back to zero. Progress shows as HUD pips."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "checkpoints"


def _parse(d):
    return tuple(tuple(p) for p in d.get("cps", []))


@register
class Checkpoints(Component):
    name = N
    tier = 3
    layer = 31
    place_order = 76
    roles = {"checkpoint": (C.AZURE, "ring"), "checkpoint_next": ("@checkpoint", "full")}

    def place(self, dr):
        path = dr.path()
        if not path:
            return False
        n = 2 if dr.teaching else 3
        reach = dr.reach(dr.start)
        cand = sorted(c for c in reach if c not in dr.occupied and c not in path)
        if len(cand) < n:
            return False
        cps = []
        for _ in range(n):
            c = dr.pick_far(cand, set(path) | set(cps), 0.4)
            if c is None:
                return False
            cps.append(dr.claim(c))
            cand.remove(c)
        # order them so the obvious nearest-first sweep is wrong at least once
        dr.rng.shuffle(cps)
        dr.data[N] = {"cps": [list(c) for c in cps]}
        return True

    def init_state(self, level, state):
        state.c[N] = 0

    def on_enter(self, level, state, pos, d, events):
        cps = static(level, N, _parse)
        k = state.c[N]
        if k < len(cps) and pos == cps[k]:
            state.c[N] = k + 1
            events.append("checkpoint")
        elif pos in cps[k + 1:]:
            if k:
                events.append("checkpoints_reset")
            state.c[N] = 0

    def win_ok(self, level, state):
        return state.c[N] == len(static(level, N, _parse))

    def draw(self, level, state, cv):
        cps = static(level, N, _parse)
        k = state.c[N]
        for i, p in enumerate(cps[k:], k):
            cv.cell(p, "checkpoint_next" if i == k else "checkpoint")

    def hud(self, level, state):
        return [("checkpoint_next", state.c[N], len(static(level, N, _parse)))]
