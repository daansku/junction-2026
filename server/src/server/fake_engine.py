"""Fake engine: walls + goal + move budget, implementing contracts/engine_api.py.

Used for fixtures and as the server's fallback until the `engine` package lands.
Deterministic: same spec -> byte-identical frames. No global random, no builtin hash().
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional

ENGINE_VERSION = "fake-0.1"
SIZE = 64
GRID = 10          # logical grid is GRID x GRID
CELL = 6           # pixels per cell
HUD_ROWS = 4       # rows 0..3
OFFSET_X = (SIZE - GRID * CELL) // 2  # 2

# palette indices (contracts/palette.json)
BG, BLUE, RED, GREEN, YELLOW, GREY, WHITE, DARK = 0, 1, 2, 3, 4, 5, 10, 11


class Action(str, Enum):
    RESET = "RESET"
    ACTION1 = "ACTION1"
    ACTION2 = "ACTION2"
    ACTION3 = "ACTION3"
    ACTION4 = "ACTION4"
    ACTION5 = "ACTION5"
    ACTION6 = "ACTION6"
    ACTION7 = "ACTION7"


MOVES = {Action.ACTION1: (0, -1), Action.ACTION2: (0, 1), Action.ACTION3: (-1, 0), Action.ACTION4: (1, 0)}
AVAILABLE = [Action.RESET, Action.ACTION1, Action.ACTION2, Action.ACTION3, Action.ACTION4]


@dataclass(frozen=True)
class GameSpec:
    family: str = "gridworld"
    seed: int = 0
    n_levels: int = 6
    difficulty: int = 2
    rules: Optional[list] = None
    skin_shuffle: bool = True


def _rng(*parts: Any) -> random.Random:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def game_id_for(spec: GameSpec) -> str:
    h = hashlib.sha1(json.dumps(asdict(spec), sort_keys=True).encode()).hexdigest()[:8]
    return f"{spec.family}-s{spec.seed}-d{spec.difficulty}-l{spec.n_levels}-{h}"


def _bfs(walls: frozenset, start: tuple, goal: tuple) -> Optional[list[str]]:
    prev: dict[tuple, Optional[tuple]] = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            path = []
            while prev[cur] is not None:
                p, a = prev[cur]
                path.append(a)
                cur = p
            return path[::-1]
        for a, (dx, dy) in MOVES.items():
            nx, ny = cur[0] + dx, cur[1] + dy
            if 0 <= nx < GRID and 0 <= ny < GRID and (nx, ny) not in walls and (nx, ny) not in prev:
                prev[(nx, ny)] = (cur, a.value)
                q.append((nx, ny))
    return None


@dataclass(frozen=True)
class Level:
    walls: frozenset
    start: tuple
    goal: tuple
    optimal_path: tuple
    budget: int


def _make_level(spec: GameSpec, index: int) -> Level:
    density = {1: 0.18, 2: 0.26, 3: 0.32}.get(spec.difficulty, 0.26)
    slack = {1: 3.0, 2: 2.0, 3: 1.5}.get(spec.difficulty, 2.0)
    for attempt in range(1000):
        r = _rng(spec.seed, spec.difficulty, index, attempt)
        cells = [(x, y) for y in range(GRID) for x in range(GRID)]
        walls = frozenset(c for c in cells if r.random() < density)
        free = [c for c in cells if c not in walls]
        if len(free) < 2:
            continue
        start, goal = r.sample(free, 2)
        path = _bfs(walls, start, goal)
        if path and len(path) >= 4 + index:
            return Level(walls, start, goal, tuple(path), math.ceil(len(path) * slack))
    raise RuntimeError("could not generate level")


class FakeGame:
    def __init__(self, spec: GameSpec):
        self.spec = spec
        self.game_id = game_id_for(spec)
        self.levels = [_make_level(spec, i) for i in range(spec.n_levels)]
        self.level = 0
        self.resets = 0
        self.state = "NOT_FINISHED"
        self.events: list[str] = []
        self._start_level()

    # --- contract ---
    def reset(self) -> list[str]:
        self.level = 0
        self.resets = 0
        self.state = "NOT_FINISHED"
        self.events = []
        self._start_level()
        return self.frame()

    def step(self, action: Action | str, x: Optional[int] = None, y: Optional[int] = None) -> list[str]:
        action = Action(action)
        self.events = []
        if action == Action.RESET:
            if self.state != "WIN":
                self.resets += 1
                self.state = "NOT_FINISHED"
                self._start_level()
                self.events.append("reset")
            return self.frame()
        if self.state != "NOT_FINISHED" or action not in MOVES:
            return self.frame()
        lv = self.levels[self.level]
        dx, dy = MOVES[action]
        nx, ny = self.pos[0] + dx, self.pos[1] + dy
        self.moves_used += 1
        if 0 <= nx < GRID and 0 <= ny < GRID and (nx, ny) not in lv.walls:
            self.pos = (nx, ny)
        else:
            self.events.append("bump")
        if self.pos == lv.goal:
            self.events.append("level_complete")
            if self.level + 1 >= len(self.levels):
                self.state = "WIN"
                self.events.append("win")
            else:
                self.level += 1
                self._start_level()
        elif self.moves_used >= lv.budget:
            self.state = "GAME_OVER"
            self.events.append("out_of_moves")
        return self.frame()

    def truth(self) -> dict:
        lv = self.levels[self.level]
        return {
            "state": self.state,
            "level": self.level + 1,
            "levels_total": len(self.levels),
            "moves_used": self.moves_used,
            "move_budget": lv.budget,
            "resets": self.resets,
            "active_rules": ["walls", "goal", "move_budget"],
            "new_rule": "walls" if self.level == 0 else None,
            "events": list(self.events),
            "optimal_moves": len(lv.optimal_path),
        }

    def describe(self) -> dict:
        return {
            "game_id": self.game_id,
            "spec": asdict(self.spec),
            "engine_version": ENGINE_VERSION,
            "levels_total": len(self.levels),
            "available_actions": [a.value for a in AVAILABLE],
            "levels": [
                {
                    "level": i + 1,
                    "rules": ["walls", "goal", "move_budget"],
                    "new_rule": "walls" if i == 0 else None,
                    "move_budget": lv.budget,
                    "optimal_moves": len(lv.optimal_path),
                    "optimal_path": list(lv.optimal_path),
                }
                for i, lv in enumerate(self.levels)
            ],
        }

    def available_actions(self) -> list[Action]:
        return list(AVAILABLE)

    def clone(self) -> "FakeGame":
        return copy.deepcopy(self)

    def state_hash(self) -> str:
        s = json.dumps([self.level, self.pos, self.moves_used, self.state], sort_keys=True)
        return hashlib.sha1(s.encode()).hexdigest()

    def frame(self) -> list[str]:
        g = [[BG] * SIZE for _ in range(SIZE)]
        lv = self.levels[self.level]
        # HUD: remaining-moves bar on rows 1-2, level pips on the right of row 1
        remaining = max(0, lv.budget - self.moves_used)
        bar_w = 40
        filled = round(bar_w * remaining / lv.budget) if lv.budget else 0
        for y in (1, 2):
            for x in range(2, 2 + bar_w):
                g[y][x] = YELLOW if x - 2 < filled else DARK
        for i in range(len(self.levels)):
            x = 63 - 2 - (len(self.levels) - 1 - i) * 3
            g[1][x] = g[2][x] = WHITE if i < self.level else (GREEN if i == self.level else DARK)

        def cell(cx: int, cy: int, color: int, inset: int = 0) -> None:
            for yy in range(HUD_ROWS + cy * CELL + inset, HUD_ROWS + (cy + 1) * CELL - inset):
                for xx in range(OFFSET_X + cx * CELL + inset, OFFSET_X + (cx + 1) * CELL - inset):
                    g[yy][xx] = color

        for (wx, wy) in lv.walls:
            cell(wx, wy, GREY)
        cell(*lv.goal, GREEN)
        cell(*self.pos, BLUE, inset=1)
        if self.state in ("WIN", "GAME_OVER"):
            border = GREEN if self.state == "WIN" else RED
            for i in range(SIZE):
                for t in (0, 63):
                    g[t][i] = g[i][t] = border
        return ["".join("0123456789abcdef"[c] for c in row) for row in g]

    # --- internal ---
    def _start_level(self) -> None:
        self.pos = self.levels[self.level].start
        self.moves_used = 0


def make_game(spec: GameSpec) -> FakeGame:
    return FakeGame(spec)


def spec_from_game_id(game_id: str) -> GameSpec:
    """Parse gridworld-s<seed>-d<diff>-l<n>-<hash8> back into a spec (fake engine only)."""
    parts = game_id.split("-")
    if len(parts) != 5 or parts[0] != "gridworld":
        raise KeyError(game_id)
    spec = GameSpec(seed=int(parts[1][1:]), difficulty=int(parts[2][1:]), n_levels=int(parts[3][1:]))
    if game_id_for(spec) != game_id:
        raise KeyError(game_id)
    return spec


DEV_SPECS = [GameSpec(seed=s, difficulty=d, n_levels=n) for s, d, n in [(1, 1, 3), (2, 2, 6), (3, 3, 6)]]


def list_games(collection: str = "dev") -> list[dict]:
    out = []
    for spec in DEV_SPECS:
        d = FakeGame(spec).describe()
        out.append({
            "game_id": d["game_id"],
            "collection": collection,
            "spec": d["spec"],
            "engine_version": ENGINE_VERSION,
            "levels_total": d["levels_total"],
            "difficulty": spec.difficulty,
            "rules": ["walls", "goal", "move_budget"],
            "rules_per_level": [lv["rules"] for lv in d["levels"]],
            "optimal_moves_total": sum(lv["optimal_moves"] for lv in d["levels"]),
        })
    return out


def load_game(collection: str, game_id: str) -> FakeGame:
    return FakeGame(spec_from_game_id(game_id))
