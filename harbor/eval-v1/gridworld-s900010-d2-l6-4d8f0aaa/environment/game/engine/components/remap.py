"""Control remap trigger: stepping onto it toggles scrambled controls (a fixed per-level
scramble: mirror left/right, mirror up/down, or swap the axes). A HUD pip lights while
scrambled."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..core.actions import Action
from ..render import colors as C

N = "remap"
U, D, L, R = Action.ACTION1, Action.ACTION2, Action.ACTION3, Action.ACTION4
MODES = {
    "mirror_h": {L: R, R: L},
    "mirror_v": {U: D, D: U},
    "swap_axes": {U: L, L: U, D: R, R: D},
    "reverse": {U: D, D: U, L: R, R: L},
}


def _parse(d):
    return frozenset(tuple(p) for p in d.get("triggers", [])), MODES[d.get("mode", "mirror_h")]


@register
class Remap(Component):
    name = N
    tier = 2
    layer = 22
    place_order = 56
    roles = {"remapper": (C.ORANGE, "half")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 8:
            return False
        cand = [c for c in path[2:-3] if c not in dr.occupied]
        if not cand:
            return False
        trig = [dr.claim(dr.pick(cand))]
        if not dr.teaching:
            rest = [c for c in dr.free() if c not in path]
            extra = dr.pick(rest)
            if extra:
                trig.append(dr.claim(extra))
        modes = ["mirror_h", "mirror_v"] if dr.teaching else sorted(MODES)
        dr.data[N] = {"triggers": [list(t) for t in trig], "mode": dr.rng.choice(modes)}
        return True

    def init_state(self, level, state):
        state.c[N] = 0

    def remap(self, level, state, action):
        if state.c[N]:
            return static(level, N, _parse)[1].get(action, action)
        return action

    def on_enter(self, level, state, pos, d, events):
        if pos in static(level, N, _parse)[0]:
            state.c[N] ^= 1
            events.append("controls_changed")

    def draw(self, level, state, cv):
        for p in static(level, N, _parse)[0]:
            cv.cell(p, "remapper")

    def hud(self, level, state):
        return [("remapper", state.c[N], 1)]
