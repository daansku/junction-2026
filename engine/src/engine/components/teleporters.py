"""Teleporter pairs. Stepping onto one end moves you to the other end (if it is free).
The generator walls off the goal, so the pair is the only way across."""
from __future__ import annotations

from .base import Component, static
from . import register, active
from ..render import colors as C

N = "teleporters"


def _parse(d):
    link = {}
    for ax, ay, bx, by in d.get("pairs", []):
        link[(ax, ay)] = (bx, by)
        link[(bx, by)] = (ax, ay)
    return link


@register
class Teleporters(Component):
    name = N
    tier = 1
    layer = 25
    place_order = 10   # cuts the map first, other rules place into the halves
    roles = {"teleporter": (C.VIOLET, "x")}

    def place(self, dr):
        cps = dr.chokepoints(min_gap=3)
        if not cps:
            return False
        cut = dr.pick(cps)
        dr.walls.add(cut)
        side_a = dr.reach(dr.start)
        if dr.goal in side_a:
            return False
        side_b = dr.reach(dr.goal)
        a_cells = sorted(c for c in side_a if c not in dr.occupied and side_a[c] >= 2)
        b_cells = sorted(c for c in side_b if c not in dr.occupied and side_b[c] >= 2)
        a = dr.pick_far(a_cells, side_a, 0.5)
        b = dr.pick(b_cells)
        if a is None or b is None:
            return False
        pairs = [[*dr.claim(a), *dr.claim(b)]]
        if not dr.teaching and dr.difficulty >= 2:  # decoy pair inside the start side
            rest = [c for c in a_cells if c not in dr.occupied]
            if len(rest) >= 2:
                x, y = dr.rng.sample(rest, 2)
                pairs.append([*dr.claim(x), *dr.claim(y)])
        dr.data[N] = {"pairs": pairs}
        return True

    def on_enter(self, level, state, pos, d, events):
        link = static(level, N, _parse)
        dst = link.get(pos)
        if dst is None:
            return
        if any(c.blocks_object(level, state, dst) for c in active(level)):
            return
        state.pos = dst
        events.append("teleport")

    def draw(self, level, state, cv):
        for p in static(level, N, _parse):
            cv.cell(p, "teleporter")
