"""Draft level used during generation, plus geometry helpers components use to place things."""
from __future__ import annotations

import random
from collections import deque

from ..core.level import Pos

NBRS = ((0, -1), (0, 1), (-1, 0), (1, 0))


class Draft:
    def __init__(self, w: int, h: int, walls: set[Pos], start: Pos, goal: Pos,
                 rng: random.Random, difficulty: int, teaching: bool, new_rule: str | None):
        self.w, self.h = w, h
        self.walls = set(walls)
        self.start, self.goal = start, goal
        self.rng = rng
        self.difficulty = difficulty
        self.teaching = teaching
        self.new_rule = new_rule
        self.data: dict = {}
        self.occupied: set[Pos] = {start, goal}

    # ---- geometry ----------------------------------------------------------
    def inb(self, p: Pos) -> bool:
        return 0 <= p[0] < self.w and 0 <= p[1] < self.h

    def floor(self) -> list[Pos]:
        return [(x, y) for y in range(self.h) for x in range(self.w) if (x, y) not in self.walls]

    def free(self, exclude: set[Pos] | None = None) -> list[Pos]:
        ex = self.occupied | (exclude or set())
        return [p for p in self.floor() if p not in ex]

    def reach(self, src: Pos, blocked: set[Pos] | frozenset = frozenset()) -> dict[Pos, int]:
        dist = {src: 0}
        q = deque([src])
        while q:
            x, y = q.popleft()
            for dx, dy in NBRS:
                n = (x + dx, y + dy)
                if self.inb(n) and n not in self.walls and n not in blocked and n not in dist:
                    dist[n] = dist[(x, y)] + 1
                    q.append(n)
        return dist

    def path(self, src: Pos | None = None, dst: Pos | None = None,
             blocked: set[Pos] | frozenset = frozenset()) -> list[Pos] | None:
        src = src or self.start
        dst = dst or self.goal
        prev: dict[Pos, Pos | None] = {src: None}
        q = deque([src])
        while q:
            cur = q.popleft()
            if cur == dst:
                out = []
                while cur is not None:
                    out.append(cur)
                    cur = prev[cur]
                return out[::-1]
            for dx, dy in NBRS:
                n = (cur[0] + dx, cur[1] + dy)
                if self.inb(n) and n not in self.walls and n not in blocked and n not in prev:
                    prev[n] = cur
                    q.append(n)
        return None

    def chokepoints(self, min_gap: int = 2) -> list[Pos]:
        """Unoccupied cells on the start->goal path whose removal disconnects start from goal,
        at least `min_gap` steps from both ends."""
        p = self.path()
        if not p:
            return []
        out = []
        for i, c in enumerate(p):
            if i < min_gap or i > len(p) - 1 - min_gap or c in self.occupied:
                continue
            if self.goal not in self.reach(self.start, blocked={c}):
                out.append(c)
        return out

    def corridor(self, p: Pos) -> bool:
        """Exactly two open neighbours, opposite each other."""
        o = [(dx, dy) for dx, dy in NBRS if (p[0] + dx, p[1] + dy) not in self.walls
             and self.inb((p[0] + dx, p[1] + dy))]
        return len(o) == 2 and o[0][0] == -o[1][0] and o[0][1] == -o[1][1]

    def pick(self, cells: list[Pos]) -> Pos | None:
        return self.rng.choice(cells) if cells else None

    def pick_far(self, cells: list[Pos], ref: dict[Pos, int] | set[Pos], frac: float = 0.5) -> Pos | None:
        """Random cell among the `frac` share of `cells` farthest from `ref` (a distance map or
        a set of cells)."""
        if not cells:
            return None
        if isinstance(ref, dict):
            score = {c: ref.get(c, 0) for c in cells}
        else:
            score = {c: min(abs(c[0] - r[0]) + abs(c[1] - r[1]) for r in ref) if ref else 0 for c in cells}
        ranked = sorted(cells, key=lambda c: (-score[c], c))
        top = ranked[:max(1, int(len(ranked) * frac))]
        return self.rng.choice(top)

    def claim(self, p: Pos) -> Pos:
        self.occupied.add(p)
        return p
