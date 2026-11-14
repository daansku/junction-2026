"""Cracked floor (proposal auto-01): a cracked tile holds you once. After you step off it,
it collapses into a hole you can never cross again. Only matters when the route must come
back the same way, so it is always taught together with a rule that forces a detour
(collect_all, keys_doors or plates_gates)."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "cracked_floor"


def _parse(d):
    return frozenset(tuple(p) for p in d.get("cells", []))


@register
class CrackedFloor(Component):
    name = N
    tier = 2
    layer = 14
    place_order = 95   # after detour rules have placed keys/gems/plates
    requires = ("collect_all", "keys_doors", "plates_gates")
    roles = {"cracked": (C.ORANGE, "x"), "hole": (C.DARK_GREY, "full")}

    def place(self, dr):
        # put cracks on corridor cells next to placed pickups: entering a dead end over a
        # crack strands you, so the agent has to find another way in
        targets = []
        for name in ("collect_all", "keys_doors", "plates_gates"):
            d = dr.data.get(name, {})
            targets += [tuple(p) for k in ("gems", "keys", "plates") for p in d.get(k, [])]
        if not targets:
            return False
        cells = []
        for t in targets:
            p = dr.path(dr.start, t)
            if not p or len(p) < 4:
                continue
            cand = [c for c in p[1:-1] if c not in dr.occupied]
            if cand:
                cells.append(dr.claim(dr.rng.choice(cand)))
        path = dr.path() or []
        cand = [c for c in path[2:-2] if c not in dr.occupied]
        if cand and not dr.teaching:
            cells.append(dr.claim(dr.rng.choice(cand)))
        if not cells:
            return False
        dr.data[N] = {"cells": [list(c) for c in cells]}
        return True

    def init_state(self, level, state):
        state.c[N] = frozenset()   # collapsed cells

    def blocks(self, level, state, pos, d):
        return pos in state.c[N]

    def blocks_object(self, level, state, pos):
        return pos in state.c[N]

    def on_enter(self, level, state, pos, d, events):
        """Moving one step from `prev` onto `pos`: if `prev` was a crack, it collapses."""
        cracks = static(level, N, _parse)
        prev = (pos[0] - d[0], pos[1] - d[1])
        if prev in cracks and prev not in state.c[N]:
            state.c[N] = state.c[N] | {prev}
            events.append("floor_collapsed")

    def draw(self, level, state, cv):
        gone = state.c[N]
        for p in static(level, N, _parse):
            cv.cell(p, "hole" if p in gone else "cracked")
