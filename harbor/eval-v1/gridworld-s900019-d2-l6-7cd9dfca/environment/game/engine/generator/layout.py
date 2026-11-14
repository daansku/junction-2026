"""Wall layouts. Every layout has a solid border; interior style varies."""
from __future__ import annotations

import random
from collections import deque

from ..core.level import Pos

STYLES = ("open", "rooms", "maze")


def border(w: int, h: int) -> set[Pos]:
    return {(x, y) for y in range(h) for x in range(w) if x in (0, w - 1) or y in (0, h - 1)}


def open_layout(rng: random.Random, w: int, h: int, density: float) -> set[Pos]:
    walls = border(w, h)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if rng.random() < density:
                walls.add((x, y))
    return walls


def rooms_layout(rng: random.Random, w: int, h: int, density: float) -> set[Pos]:
    walls = border(w, h)
    # one vertical and one horizontal partition, each with 1-2 gaps
    vx = rng.randint(3, w - 4)
    hy = rng.randint(3, h - 4)
    for y in range(1, h - 1):
        walls.add((vx, y))
    for x in range(1, w - 1):
        walls.add((x, hy))
    segs = [[(vx, y) for y in range(1, hy)], [(vx, y) for y in range(hy + 1, h - 1)],
            [(x, hy) for x in range(1, vx)], [(x, hy) for x in range(vx + 1, w - 1)]]
    for seg in segs:
        if seg:
            walls.discard(rng.choice(seg))
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if (x, y) not in walls and x != vx and y != hy and rng.random() < density * 0.5:
                walls.add((x, y))
    return walls


def maze_layout(rng: random.Random, w: int, h: int, density: float) -> set[Pos]:
    """Recursive backtracker on odd coordinates, then knock out extra walls to add loops."""
    walls = {(x, y) for y in range(h) for x in range(w)}
    start = (1, 1)
    walls.discard(start)
    stack = [start]
    while stack:
        x, y = stack[-1]
        nbrs = [(x + dx, y + dy, x + dx // 2, y + dy // 2) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
                if 0 < x + dx < w - 1 and 0 < y + dy < h - 1 and (x + dx, y + dy) in walls]
        if not nbrs:
            stack.pop()
            continue
        nx, ny, mx, my = rng.choice(nbrs)
        walls.discard((nx, ny))
        walls.discard((mx, my))
        stack.append((nx, ny))
    interior = sorted(p for p in walls if 0 < p[0] < w - 1 and 0 < p[1] < h - 1)
    for p in interior:
        if rng.random() < max(0.0, 0.35 - density):
            walls.discard(p)
    return walls


def make_layout(rng: random.Random, style: str, w: int, h: int, density: float) -> set[Pos]:
    return {"open": open_layout, "rooms": rooms_layout, "maze": maze_layout}[style](rng, w, h, density)


def floor_cells(w: int, h: int, walls: set[Pos]) -> list[Pos]:
    return [(x, y) for y in range(h) for x in range(w) if (x, y) not in walls]


def distances(w: int, h: int, walls: set[Pos], src: Pos) -> dict[Pos, int]:
    dist = {src: 0}
    q = deque([src])
    while q:
        x, y = q.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < w and 0 <= n[1] < h and n not in walls and n not in dist:
                dist[n] = dist[(x, y)] + 1
                q.append(n)
    return dist
