"""Pushable blocks. Walking into a block pushes it one cell if the cell behind it is free
(no wall, block, closed door/gate, or goal). Otherwise you bump."""
from __future__ import annotations

from .base import Component
from . import register, active
from ..render import colors as C

N = "push_blocks"


@register
class PushBlocks(Component):
    name = N
    tier = 1
    layer = 40
    place_order = 70
    roles = {"block": (C.BROWN, "frame_dot")}

    def place(self, dr):
        path = dr.path()
        if not path:
            return False
        n = 1 if dr.teaching else min(3, 1 + dr.difficulty // 2)
        cand = [c for c in path[2:-2] if c not in dr.occupied]
        if not cand:
            return False
        blocks = [dr.claim(c) for c in dr.rng.sample(cand, min(n, len(cand)))]
        dr.data[N] = {"blocks": [list(b) for b in blocks]}
        return True

    def init_state(self, level, state):
        state.c[N] = frozenset(tuple(b) for b in level.data[N]["blocks"])

    def push(self, level, state, pos, d, events):
        blocks = state.c[N]
        if pos not in blocks:
            return None
        t = (pos[0] + d[0], pos[1] + d[1])
        if not level.in_bounds(t) or t == level.goal:
            return False
        if any(c.blocks_object(level, state, t) for c in active(level)):
            return False
        state.c[N] = (blocks - {pos}) | {t}
        events.append("pushed")
        return True

    def blocks_object(self, level, state, pos):
        return pos in state.c[N]

    def draw(self, level, state, cv):
        for b in state.c[N]:
            cv.cell(b, "block")
