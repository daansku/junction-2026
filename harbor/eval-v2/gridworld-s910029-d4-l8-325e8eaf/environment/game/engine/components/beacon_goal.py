"""Beacon goal (proposal a5-decoy-and-camouflage): two or three goal rings in different
colours. A beacon pip in the HUD shows the colour of the real one. Stepping on a decoy ring
sends you back to the start (the move still counts).

The real goal is drawn in a fresh colour and the first decoy in the game's usual goal colour,
so remembering "the goal is the orange ring" from earlier levels walks you into the decoy;
only the beacon tells you which ring is real."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "beacon_goal"
REAL_ROLE = "decoy_a"
DECOY_ROLES = ("goal", "decoy_b")


def _parse(d):
    return tuple(tuple(p) for p in d.get("decoys", []))


@register
class BeaconGoal(Component):
    name = N
    tier = 2
    layer = 20
    place_order = 30
    roles = {"decoy_a": (C.MAGENTA, "ring"), "decoy_b": (C.TEAL, "ring")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 7:
            return False
        n = 1 if dr.teaching or dr.difficulty < 3 else 2
        decoys = []
        # one decoy on the shortest path (forces a detour), others nearer the start than the goal
        cand = [c for c in path[2:-2] if c not in dr.occupied and not dr.corridor(c)]
        if not cand:
            return False
        decoys.append(dr.claim(dr.pick(cand)))
        reach = dr.reach(dr.start)
        while len(decoys) < n:
            near = sorted(c for c in reach if c not in dr.occupied and reach[c] < len(path) // 2)
            c = dr.pick(near)
            if c is None:
                break
            decoys.append(dr.claim(c))
        dr.data[N] = {"decoys": [list(p) for p in decoys]}
        return True

    def on_enter(self, level, state, pos, d, events):
        if pos in static(level, N, _parse):
            state.pos = level.start
            events.append("decoy")

    def draw(self, level, state, cv):
        for p, role in zip(static(level, N, _parse), DECOY_ROLES):
            cv.cell(p, role)

    def hud(self, level, state):
        return [(REAL_ROLE, 1, 1)]
