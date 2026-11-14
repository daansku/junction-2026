"""Keys + doors. Walking onto a key picks it up. Walking into a closed door while holding a key
opens it and uses the key up. Any key opens any door. Held keys show as HUD pips."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "keys_doors"


def _parse(d):
    return frozenset(tuple(p) for p in d.get("keys", [])), frozenset(tuple(p) for p in d.get("doors", []))


@register
class KeysDoors(Component):
    name = N
    tier = 1
    layer = 30
    place_order = 40
    roles = {"key": (C.ORANGE, "dot"), "door": ("@key", "bars")}

    def place(self, dr):
        n = 1 if dr.teaching or dr.difficulty < 3 else 2
        path = dr.path()
        cps = dr.chokepoints()
        if len(cps) < n or not path:
            return False
        order = {c: i for i, c in enumerate(path)}
        doors = sorted(dr.rng.sample(cps, n), key=order.get)
        for d in doors:
            dr.claim(d)
        keys = []
        for i in range(n):
            region = dr.reach(dr.start, blocked=set(doors[i:]))
            cand = [c for c in region if c not in dr.occupied]
            k = dr.pick_far(sorted(cand), set(path), 0.4)
            if k is None:
                return False
            keys.append(dr.claim(k))
        dr.data[N] = {"doors": [list(p) for p in doors], "keys": [list(p) for p in keys]}
        return True

    def init_state(self, level, state):
        state.c[N] = (0, frozenset(), frozenset())  # held, picked keys, opened doors

    def blocks(self, level, state, pos, d):
        _, doors = static(level, N, _parse)
        held, _, opened = state.c[N]
        return pos in doors and pos not in opened and held == 0

    def blocks_object(self, level, state, pos):
        _, doors = static(level, N, _parse)
        return pos in doors and pos not in state.c[N][2]

    def on_enter(self, level, state, pos, d, events):
        keys, doors = static(level, N, _parse)
        held, picked, opened = state.c[N]
        if pos in keys and pos not in picked:
            state.c[N] = (held + 1, picked | {pos}, opened)
            events.append("picked_key")
        elif pos in doors and pos not in opened:
            state.c[N] = (held - 1, picked, opened | {pos})
            events.append("opened_door")

    def draw(self, level, state, cv):
        keys, doors = static(level, N, _parse)
        _, picked, opened = state.c[N]
        for k in keys - picked:
            cv.cell(k, "key")
        for d in doors - opened:
            cv.cell(d, "door")

    def hud(self, level, state):
        keys, _ = static(level, N, _parse)
        return [("key", state.c[N][0], len(keys))]
