"""Game: a sequence of levels played through the ARC-AGI-3 style action interface (§4.3).

Level numbers in Truth are 1-based (`level` 1..levels_total). `moves_used` counts actions in
the current attempt of the current level; `RESET` restarts the current level and is counted
in `resets`. After GAME_OVER only RESET changes anything; after WIN nothing does.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .actions import MOVE_ACTIONS, Action, parse_action
from .level import Level, State
from .rng import short_hash
from .step import LEVEL_WON, LOST, initial_state, step_level, uses_interact
from .version import ENGINE_VERSION

Frame = list[str]
NOT_FINISHED, WIN, GAME_OVER = "NOT_FINISHED", "WIN", "GAME_OVER"


@dataclass
class GameSpec:
    family: str = "gridworld"
    seed: int = 0
    n_levels: int = 6
    difficulty: int = 2
    rules: list[str] | None = None   # None -> curriculum picks
    skin_shuffle: bool = True


class Game:
    def __init__(self, spec: GameSpec, levels: list[Level], skin: dict[str, tuple[int, str]],
                 engine_version: str = ENGINE_VERSION, game_id: str | None = None):
        self.spec = spec
        self.levels = levels
        self.skin = {k: (int(v[0]), str(v[1])) for k, v in skin.items()}
        self.engine_version = engine_version
        self.game_id = game_id or self._make_id()
        self.reset()

    # ---- identity / serialisation ---------------------------------------
    def _make_id(self) -> str:
        body = json.dumps({"levels": [lv.to_dict() for lv in self.levels], "skin": self.skin,
                           "engine_version": self.engine_version}, sort_keys=True)
        s = self.spec
        return f"{s.family}-s{s.seed}-d{s.difficulty}-l{len(self.levels)}-{short_hash(body)}"

    def to_dict(self) -> dict[str, Any]:
        return {"game_id": self.game_id, "spec": asdict(self.spec),
                "engine_version": self.engine_version,
                "skin": {k: list(v) for k, v in sorted(self.skin.items())},
                "levels": [lv.to_dict() for lv in self.levels]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Game":
        return cls(GameSpec(**d["spec"]), [Level.from_dict(x) for x in d["levels"]],
                   {k: tuple(v) for k, v in d["skin"].items()}, d["engine_version"], d["game_id"])

    # ---- play ------------------------------------------------------------
    @property
    def level(self) -> Level:
        return self.levels[min(self.idx, len(self.levels) - 1)]

    def reset(self) -> Frame:
        """Start (or restart) the whole game at level 1."""
        self.idx = 0
        self.status = NOT_FINISHED
        self.resets = 0
        self.actions_total = 0
        self.events: list[str] = []
        self.state = initial_state(self.levels[0])
        return self.frame()

    def goto_level(self, level: int) -> Frame:
        """Jump to the start of level `level` (1-based). UI/gallery/debug only, never for
        scored play."""
        self.reset()
        self.idx = max(0, min(len(self.levels) - 1, level - 1))
        self.state = initial_state(self.level)
        return self.frame()

    def available_actions(self) -> list[Action]:
        """Action is a str enum, so members serialise as "ACTION1" etc."""
        if self.status == WIN:
            return []
        if self.status == GAME_OVER:
            return [Action.RESET]
        acts = [Action.RESET] + list(MOVE_ACTIONS)
        if uses_interact(self.level):
            acts.append(Action.ACTION5)
        return acts

    def step(self, action: Action | str | int, x: int | None = None, y: int | None = None) -> Frame:
        """x, y are for ACTION6 (click), unused in v1. Unavailable actions are free no-ops."""
        a = parse_action(action)
        if a not in self.available_actions():
            self.events = ["noop"]
            return self.frame()
        self.actions_total += 1
        if a == Action.RESET:
            self.resets += 1
            self.status = NOT_FINISHED
            self.state = initial_state(self.level)
            self.events = ["reset"]
            return self.frame()
        self.state, self.events, out = step_level(self.level, self.state, a)
        if out == LEVEL_WON:
            self.events.append("level_complete")
            self.idx += 1
            if self.idx >= len(self.levels):
                self.status = WIN
                self.events.append("game_won")
            else:
                self.state = initial_state(self.level)
        elif out == LOST:
            self.status = GAME_OVER
            self.events.append("level_lost")
        return self.frame()

    def frame(self) -> Frame:
        from ..render.frame import render
        return render(self.level, self.state, self.skin, self.idx, len(self.levels), self.status)

    # ---- hidden information ------------------------------------------------
    def truth(self) -> dict[str, Any]:
        lv = self.level
        return {
            "state": self.status,
            "level": min(self.idx + 1, len(self.levels)),
            "levels_total": len(self.levels),
            "levels_completed": self.idx,
            "moves_used": self.state.moves,
            "move_budget": lv.move_budget,
            "resets": self.resets,
            "actions_total": self.actions_total,
            "active_rules": list(lv.rules),
            "new_rule": lv.new_rule,
            "events": list(self.events),
            "optimal_moves": lv.optimal_moves,
        }

    def describe(self) -> dict[str, Any]:
        s = self.spec
        return {
            "game_id": self.game_id, "family": s.family, "seed": s.seed,
            "difficulty": s.difficulty, "levels_total": len(self.levels),
            "available_actions": [a.value for a in self._all_actions()],
            "engine_version": self.engine_version, "spec": asdict(s),
            "rules": sorted({r for lv in self.levels for r in lv.rules}),
            "optimal_moves_total": sum(lv.optimal_moves for lv in self.levels),
            "levels": [{
                "level": i + 1, "rules": list(lv.rules), "new_rule": lv.new_rule,
                "w": lv.w, "h": lv.h, "layout": lv.data.get("layout"),
                "move_budget": lv.move_budget, "optimal_moves": lv.optimal_moves,
                "optimal_path": list(lv.optimal_path),
                "start": list(lv.start), "goal": list(lv.goal),
                **_trace_path(lv),
            } for i, lv in enumerate(self.levels)],
        }

    def _all_actions(self) -> list[Action]:
        acts = [Action.RESET] + list(MOVE_ACTIONS)
        if any(uses_interact(lv) for lv in self.levels):
            acts.append(Action.ACTION5)
        return acts

    def meta(self) -> dict[str, Any]:
        """Compact metadata for catalogues (list_games)."""
        return {"game_id": self.game_id, "spec": asdict(self.spec),
                "engine_version": self.engine_version, "levels_total": len(self.levels),
                "difficulty": self.spec.difficulty,
                "rules": sorted({r for lv in self.levels for r in lv.rules}),
                "rules_per_level": [list(lv.rules) for lv in self.levels],
                "optimal_moves_total": sum(lv.optimal_moves for lv in self.levels),
                "new_rules": [lv.new_rule for lv in self.levels],
                "optimal_moves": [lv.optimal_moves for lv in self.levels],
                "move_budgets": [lv.move_budget for lv in self.levels]}

    # ---- solver support ------------------------------------------------------
    def clone(self) -> "Game":
        g = object.__new__(Game)
        g.__dict__.update(self.__dict__)
        g.state = self.state.copy()
        g.events = list(self.events)
        return g

    def state_hash(self) -> str:
        body = f"{self.game_id}|{self.idx}|{self.status}|{self.state.canonical()}"
        return hashlib.sha1(body.encode()).hexdigest()


def _trace_path(lv: Level) -> dict[str, Any]:
    """Player cell after each optimal action (slides/teleports resolved) plus the same in
    frame pixels: [x, y, cell_size] of the cell's top-left, honouring map rotation."""
    from ..render.canvas import Canvas
    s = initial_state(lv)
    cells, pixels = [], []
    cv = Canvas({}, 0)
    for a in lv.optimal_path:
        s, _, _ = step_level(lv, s, parse_action(a))
        cells.append(list(s.pos))
        cv.set_grid(lv.w, lv.h, rot=int(s.c.get("rotation", 0)), stable="rotation" in lv.rules)
        x, y = cv._xf(s.pos[0], s.pos[1], lv.w, lv.h)
        pixels.append([cv.ox + x * cv.cs, cv.oy + y * cv.cs, cv.cs])
    cv.set_grid(lv.w, lv.h, stable="rotation" in lv.rules)
    return {"optimal_positions": cells, "optimal_pixels": pixels,
            "start_pixel": [cv.ox + lv.start[0] * cv.cs, cv.oy + lv.start[1] * cv.cs, cv.cs]}


# ---- constructors ---------------------------------------------------------------
def make_game(spec: GameSpec) -> Game:
    from ..generator import generate_levels
    from ..generator.skin import make_skin
    levels = generate_levels(spec.seed, spec.family, spec.difficulty, spec.n_levels, spec.rules)
    used = sorted({r for lv in levels for r in lv.rules})
    return Game(spec, levels, make_skin(spec.seed, spec.family, spec.skin_shuffle, used))


def collections_dir() -> Path:
    env = os.environ.get("ENGINE_COLLECTIONS_DIR")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        p = parent / "data" / "collections"
        if p.is_dir():
            return p
    return Path.cwd() / "data" / "collections"


def collection_path(collection: str | Path) -> Path:
    p = Path(collection)
    if p.suffix == ".json" and p.exists():
        return p
    return collections_dir() / f"{collection}.json"


@lru_cache(maxsize=16)
def _load_collection(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_collection(collection: str | Path) -> dict[str, Any]:
    return _load_collection(str(collection_path(collection).resolve()))


def list_games(collection: str | Path) -> list[dict[str, Any]]:
    """Metadata for every game in a collection (contracts/engine_api.py). Fresh dicts each call
    (callers may annotate them); the expensive part is cached per collection file."""
    return [dict(m) for m in _list_games(str(collection_path(collection).resolve()))]


@lru_cache(maxsize=16)
def _list_games(path: str) -> tuple[dict[str, Any], ...]:
    return tuple(Game.from_dict(g).meta() for g in _load_collection(path)["games"])


@lru_cache(maxsize=16)
def _index(path: str) -> dict[str, dict[str, Any]]:
    return {g["game_id"]: g for g in _load_collection(path)["games"]}


def load_game(collection: str | Path, game_id: str) -> Game:
    g = _index(str(collection_path(collection).resolve())).get(game_id)
    if g is None:
        raise KeyError(f"{game_id} not in collection {collection}")
    return Game.from_dict(g)
