"""Patrolling enemies: each walks back and forth along a fixed straight track (3-5 cells),
one cell per counted action, moving at the same time as you. Ending your move on an enemy,
or swapping places with one, loses the level."""
from __future__ import annotations

from .base import Component, static
from . import register
from ..render import colors as C

N = "enemies"
CLOCK = 24  # lcm of all possible ping-pong periods (2, 4, 6, 8)


def _parse(d):
    return tuple(tuple(tuple(p) for p in tr) for tr in d.get("tracks", []))


def at(track, t):
    n = len(track)
    if n == 1:
        return track[0]
    period = 2 * (n - 1)
    k = t % period
    return track[k if k < n else period - k]


@register
class Enemies(Component):
    name = N
    tier = 3
    layer = 80
    place_order = 92
    roles = {"enemy": (C.MAGENTA, "x")}

    def place(self, dr):
        path = dr.path()
        if not path or len(path) < 8:
            return False
        n = 1 if dr.teaching else 1 + dr.difficulty // 2
        tracks = []
        for _ in range(n * 4):
            if len(tracks) >= n:
                break
            cx, cy = dr.rng.choice(path[3:-2])
            d = dr.rng.choice(((1, 0), (0, 1)))
            tr = [(cx, cy)]
            for sgn in (1, -1):
                x, y = cx, cy
                while len(tr) < 5:
                    x, y = x + sgn * d[0], y + sgn * d[1]
                    if not dr.inb((x, y)) or (x, y) in dr.walls or (x, y) in dr.occupied:
                        break
                    if sgn == 1:
                        tr.append((x, y))
                    else:
                        tr.insert(0, (x, y))
            if len(tr) >= 3 and dr.start not in tr and dr.goal not in tr:
                tracks.append(tr)
        if not tracks:
            return False
        dr.data[N] = {"tracks": [[list(p) for p in tr] for tr in tracks]}
        return True

    def init_state(self, level, state):
        state.c[N] = (0, 0)  # (clock, caught)

    def on_enter(self, level, state, pos, d, events):
        t, caught = state.c[N]
        prev = (pos[0] - d[0], pos[1] - d[1])
        for tr in static(level, N, _parse):
            if at(tr, t) == pos and at(tr, t + 1) == prev:
                state.c[N] = (t, 1)
                events.append("caught")

    def on_step(self, level, state, events):
        t, caught = state.c[N]
        t = (t + 1) % CLOCK
        if any(at(tr, t) == state.pos for tr in static(level, N, _parse)):
            caught = 1
            events.append("caught")
        state.c[N] = (t, caught)

    def lost(self, level, state):
        return bool(state.c[N][1])

    def draw(self, level, state, cv):
        t = state.c[N][0]
        for tr in static(level, N, _parse):
            cv.cell(at(tr, t), "enemy")
