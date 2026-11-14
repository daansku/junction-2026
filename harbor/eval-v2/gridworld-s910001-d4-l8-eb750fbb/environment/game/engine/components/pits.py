"""Pits: you can't walk into a pit. Push a block into it and the block fills the pit, which
becomes floor for good. Always taught together with push_blocks."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "pits"
PB = "push_blocks"


def _parse(d):
    return frozenset(tuple(p) for p in d.get("pits", []))


@register
class Pits(Component):
    name = N
    tier = 3
    layer = 13
    place_order = 72  # right after push_blocks
    requires = (PB,)
    roles = {"pit": (C.WHITE, "checker")}

    def place(self, dr):
        if PB not in dr.data:
            return False
        blocks = [tuple(b) for b in dr.data[PB]["blocks"]]
        path = dr.path() or []
        if not path:
            return False
        first = min(path.index(b) for b in blocks if b in path) if any(b in path for b in blocks) else None
        if first is None:
            return False
        # a pit on the route past the first block, ideally a chokepoint so it must be filled
        chokes = [c for c in dr.chokepoints() if path.index(c) > first + 1]
        cand = chokes or [c for c in path[first + 2:-1] if c not in dr.occupied]
        n = 1 if dr.teaching else min(2, len(blocks))
        pits = []
        for c in cand[:]:
            if len(pits) >= n:
                break
            if c not in dr.occupied:
                pits.append(dr.claim(c))
        if not pits:
            return False
        dr.data[N] = {"pits": [list(p) for p in pits]}
        return True

    def init_state(self, level, state):
        state.c[N] = frozenset()  # filled pits

    def _open(self, level, state, pos):
        return pos in static(level, N, _parse) and pos not in state.c[N]

    def blocks(self, level, state, pos, d):
        return self._open(level, state, pos)

    def on_step(self, level, state, events):
        blocks = state.c.get(PB)
        if not blocks:
            return
        sunk = {b for b in blocks if self._open(level, state, b)}
        if sunk:
            state.c[PB] = blocks - sunk
            state.c[N] = state.c[N] | sunk
            events.append("pit_filled")

    def draw(self, level, state, cv):
        for p in static(level, N, _parse) - state.c[N]:
            cv.cell(p, "pit")
