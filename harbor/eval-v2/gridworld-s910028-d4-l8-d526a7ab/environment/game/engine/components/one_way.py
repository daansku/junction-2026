"""One-way tiles. A tile can only be entered moving in its arrow's direction."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "one_way"
DIRV = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
VDIR = {v: k for k, v in DIRV.items()}


def _parse(d):
    return {(t[0], t[1]): DIRV[t[2]] for t in d.get("tiles", [])}


@register
class OneWay(Component):
    name = N
    tier = 1
    layer = 20
    place_order = 65
    roles = {"one_way": (C.AZURE, "arrow_up")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 6:
            return False
        n_against = 1 if dr.teaching else 1 + dr.difficulty // 2
        n_along = 1 if dr.teaching else dr.difficulty
        idx = [i for i in range(2, len(path) - 1) if path[i] not in dr.occupied]
        if len(idx) < n_against + n_along:
            return False
        chosen = dr.rng.sample(idx, n_against + n_along)
        tiles = []
        for j, i in enumerate(sorted(chosen)):
            step = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
            against = j < n_against if dr.rng.random() < 0.5 else j >= len(chosen) - n_against
            d = (-step[0], -step[1]) if against else step
            tiles.append([*dr.claim(path[i]), VDIR[d]])
        dr.data[N] = {"tiles": tiles}
        return True

    def blocks(self, level, state, pos, d):
        want = static(level, N, _parse).get(pos)
        return want is not None and want != d

    def draw(self, level, state, cv):
        for p, d in static(level, N, _parse).items():
            cv.cell(p, "one_way", sprite=f"arrow_{VDIR[d]}")
