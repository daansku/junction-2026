"""Tiny stand-in game so the harness can be built before the engine lands.

Speaks the same shapes as the real engine: 64x64 hex frames, RESET + ACTION1..4,
Truth dict, describe() with an optimal path per level. Walls + goal + budget bar.
Delete once engine.make_game is available (the HTTP client never uses this).
"""
from __future__ import annotations

import hashlib
import random
from collections import deque

ACTIONS = ["RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4"]
MOVES = {"ACTION1": (0, -1), "ACTION2": (0, 1), "ACTION3": (-1, 0), "ACTION4": (1, 0)}
N, CELL, TOP = 10, 6, 4  # 10x10 logical grid, 6px cells, HUD rows 0-3
BG, WALL, PLAYER, GOAL, BAR, BAR_BG, WIN_C, LOSE_C = 0, 5, 1, 3, 4, 8, 3, 2


def _rng(seed: int, level: int) -> random.Random:
    return random.Random(int(hashlib.sha256(f"mock:{seed}:{level}".encode()).hexdigest()[:16], 16))


def _bfs(walls, start, goal):
    q, prev = deque([start]), {start: None}
    while q:
        p = q.popleft()
        if p == goal:
            path = []
            while prev[p] is not None:
                p, a = prev[p]
                path.append(a)
            return path[::-1]
        for a, (dx, dy) in MOVES.items():
            n = (p[0] + dx, p[1] + dy)
            if 0 <= n[0] < N and 0 <= n[1] < N and n not in walls and n not in prev:
                prev[n] = (p, a)
                q.append(n)
    return None


def _make_level(seed: int, level: int):
    rng = _rng(seed, level)
    while True:
        walls = {(rng.randrange(N), rng.randrange(N)) for _ in range(18 + 4 * level)}
        free = [(x, y) for x in range(N) for y in range(N) if (x, y) not in walls]
        start, goal = rng.sample(free, 2)
        path = _bfs(walls, start, goal)
        if path and len(path) >= 5 + 2 * level:
            return {"walls": walls, "start": start, "goal": goal, "optimal": path,
                    "budget": int(len(path) * 2) + 4}


class MockGame:
    def __init__(self, seed: int = 0, n_levels: int = 3):
        self.seed, self.n_levels = seed, n_levels
        self.levels = [_make_level(seed, i) for i in range(n_levels)]
        self.game_id = f"mock-s{seed}-l{n_levels}"
        self.level = 0
        self.resets = 0
        self.total_moves = 0
        self.state = "NOT_FINISHED"
        self._start_level()

    def _start_level(self):
        lv = self.levels[self.level]
        self.pos, self.moves, self.events = lv["start"], 0, []
        self.level_over = False

    def reset(self) -> list[str]:
        return self.frame()

    def step(self, action: str) -> list[str]:
        self.events = []
        if self.state == "WIN":
            return self.frame()
        if action == "RESET":
            self.resets += 1
            self.state = "NOT_FINISHED"
            self._start_level()
            return self.frame()
        if self.state == "GAME_OVER" or action not in MOVES:
            return self.frame()
        lv = self.levels[self.level]
        dx, dy = MOVES[action]
        n = (self.pos[0] + dx, self.pos[1] + dy)
        self.moves += 1
        self.total_moves += 1
        if 0 <= n[0] < N and 0 <= n[1] < N and n not in lv["walls"]:
            self.pos = n
        else:
            self.events.append("bump")
        if self.pos == lv["goal"]:
            self.events.append("level_complete")
            if self.level + 1 == self.n_levels:
                self.state = "WIN"
            else:
                self.level += 1
                self._start_level()
        elif self.moves >= lv["budget"]:
            self.state = "GAME_OVER"
        return self.frame()

    def frame(self) -> list[str]:
        g = [[BG] * 64 for _ in range(64)]
        lv = self.levels[self.level]
        # HUD: remaining-moves bar (rows 0-1), level pips (row 3)
        left = max(0, lv["budget"] - self.moves)
        filled = round(60 * left / lv["budget"])
        for x in range(2, 62):
            for y in (0, 1):
                g[y][x] = BAR if x - 2 < filled else BAR_BG
        for i in range(self.n_levels):
            g[3][2 + 3 * i] = GOAL if i < self.level or self.state == "WIN" else BAR_BG

        def fill(cell, c):
            x0, y0 = 2 + cell[0] * CELL, TOP + cell[1] * CELL
            for y in range(y0, y0 + CELL):
                for x in range(x0, x0 + CELL):
                    g[y][x] = c

        for w in lv["walls"]:
            fill(w, WALL)
        fill(lv["goal"], GOAL)
        fill(self.pos, PLAYER)
        if self.state in ("WIN", "GAME_OVER"):
            c = WIN_C if self.state == "WIN" else LOSE_C
            for i in range(64):
                g[TOP][i] = g[63][i] = g[min(63, TOP + i)][0] = g[min(63, TOP + i)][63] = c
        return ["".join("%x" % v for v in row) for row in g]

    def truth(self) -> dict:
        lv = self.levels[self.level]
        return {"state": self.state, "level": self.level + 1, "levels_total": self.n_levels,
                "moves_used": self.moves, "move_budget": lv["budget"], "resets": self.resets,
                "active_rules": ["walls", "goal"], "new_rule": None, "events": self.events,
                "optimal_moves": len(lv["optimal"])}

    def available_actions(self) -> list[str]:
        return list(ACTIONS)

    def clone(self) -> "MockGame":
        import copy
        return copy.deepcopy(self)

    def state_hash(self) -> str:
        return hashlib.sha1(repr((self.level, self.pos, self.moves, self.state)).encode()).hexdigest()

    def describe(self) -> dict:
        return {"game_id": self.game_id, "engine_version": "mock-0", "levels_total": self.n_levels,
                "spec": {"family": "mock", "seed": self.seed, "n_levels": self.n_levels},
                "available_actions": list(ACTIONS),
                "levels": [{"level": i + 1, "rules": ["walls", "goal"], "new_rule": None, "move_budget": lv["budget"],
                            "optimal_path": list(lv["optimal"]), "optimal_moves": len(lv["optimal"])}
                           for i, lv in enumerate(self.levels)]}


# contract-shaped entry points so engine_adapter can fall back to this module
class GameSpec:
    def __init__(self, family="mock", seed=0, n_levels=3, difficulty=1, rules=None, skin_shuffle=True):
        self.family, self.seed, self.n_levels, self.difficulty = family, seed, n_levels, difficulty


def make_game(spec) -> MockGame:
    return MockGame(spec.seed, spec.n_levels)
