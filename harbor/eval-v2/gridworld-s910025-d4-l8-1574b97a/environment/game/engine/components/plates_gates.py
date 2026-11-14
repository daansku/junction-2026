"""Pressure plates + gates. Stepping onto any plate flips every gate (open <-> closed).
Gates may start open or closed, so the order you cross gates and plates matters."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "plates_gates"


def _parse(d):
    plates = frozenset(tuple(p) for p in d.get("plates", []))
    gates = {(g[0], g[1]): bool(g[2]) for g in d.get("gates", [])}  # pos -> starts open
    return plates, gates


@register
class PlatesGates(Component):
    name = N
    tier = 1
    layer = 30
    place_order = 45
    roles = {"plate": (C.TEAL, "checker"), "gate": ("@plate", "hbar")}

    def place(self, dr):
        path = dr.path()
        cps = dr.chokepoints()
        if not cps or not path:
            return False
        n_gates = 1 if dr.teaching or dr.difficulty < 2 else min(len(cps), dr.rng.choice((1, 2)))
        order = {c: i for i, c in enumerate(path)}
        gates = sorted(dr.rng.sample(cps, n_gates), key=order.get)
        for g in gates:
            dr.claim(g)
        gate_open = [False] + [dr.rng.random() < 0.5 for _ in gates[1:]]
        region = dr.reach(dr.start, blocked={gates[0]})
        cand = sorted(c for c in region if c not in dr.occupied)
        p = dr.pick_far(cand, set(path), 0.4)
        if p is None:
            return False
        plates = [dr.claim(p)]
        if n_gates > 1:  # second plate anywhere reachable once the first gate is open
            cand = sorted(c for c in dr.reach(dr.start) if c not in dr.occupied)
            p2 = dr.pick(cand)
            if p2:
                plates.append(dr.claim(p2))
        dr.data[N] = {"plates": [list(p) for p in plates],
                      "gates": [[g[0], g[1], int(o)] for g, o in zip(gates, gate_open)]}
        return True

    def init_state(self, level, state):
        state.c[N] = 0  # number of flips mod 2

    def _closed(self, level, state, pos):
        _, gates = static(level, N, _parse)
        return pos in gates and gates[pos] == bool(state.c[N])

    def blocks(self, level, state, pos, d):
        return self._closed(level, state, pos)

    def blocks_object(self, level, state, pos):
        return self._closed(level, state, pos)

    def on_enter(self, level, state, pos, d, events):
        plates, _ = static(level, N, _parse)
        if pos in plates:
            state.c[N] ^= 1
            events.append("pressed_plate")

    def draw(self, level, state, cv):
        plates, gates = static(level, N, _parse)
        for p in plates:
            cv.cell(p, "plate")
        for g in gates:
            if self._closed(level, state, g):
                cv.cell(g, "gate")
