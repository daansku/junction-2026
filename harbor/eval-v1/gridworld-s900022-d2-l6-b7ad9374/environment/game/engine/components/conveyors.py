"""Conveyor belts: after your move settles on a belt, it carries you one cell in its arrow
direction, and keeps carrying while you stay on belts (until something blocks)."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "conveyors"
DIRV = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
VDIR = {v: k for k, v in DIRV.items()}


def _parse(d):
    return {(t[0], t[1]): DIRV[t[2]] for t in d.get("belts", [])}


@register
class Conveyors(Component):
    name = N
    tier = 3
    layer = 16
    place_order = 66
    roles = {"belt": (C.TEAL, "arrow_up")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 8:
            return False
        n_runs = 1 if dr.teaching else 1 + dr.difficulty // 2
        belts = {}
        for _ in range(n_runs):
            i = dr.rng.randrange(2, len(path) - 3)
            step = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
            d = (-step[0], -step[1]) if dr.rng.random() < 0.6 else (step[1], step[0])
            length = dr.rng.randint(2, 4)
            x, y = path[i]
            for _ in range(length):
                p = (x, y)
                if not dr.inb(p) or p in dr.walls or p in dr.occupied or p in belts:
                    break
                belts[p] = d
                x, y = x + d[0], y + d[1]
        if len(belts) < 2:
            return False
        for p in belts:
            dr.claim(p)
        dr.data[N] = {"belts": [[p[0], p[1], VDIR[d]] for p, d in sorted(belts.items())]}
        return True

    def drift(self, level, state, pos):
        return static(level, N, _parse).get(pos)

    def draw(self, level, state, cv):
        for p, d in static(level, N, _parse).items():
            cv.cell(p, "belt", sprite=f"arrow_{VDIR[d]}")
