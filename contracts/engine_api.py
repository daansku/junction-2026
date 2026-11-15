"""Engine API contract (PLAN.md section 4.3). Frozen at G0; additive changes only, via a request to A2.

A1 implements this in `engine` (import path: `from engine import make_game, load_game, GameSpec, Action`).
A2, A3 and A5 code against these types. This file is a reference: it has no dependencies and is
importable on its own (`python contracts/engine_api.py` runs a self-check).

Frame wire format: list of 64 strings, each 64 lowercase hex chars (one char per cell, value 0-15),
row 0 at the top. Palette: contracts/palette.json.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Protocol, TypedDict

FRAME_SIZE = 64
N_COLORS = 16

Frame = list[str]  # 64 rows x 64 hex chars


class Action(str, enum.Enum):
    RESET = "RESET"      # restart the current level (counted)
    ACTION1 = "ACTION1"  # up
    ACTION2 = "ACTION2"  # down
    ACTION3 = "ACTION3"  # left
    ACTION4 = "ACTION4"  # right
    ACTION5 = "ACTION5"  # interact (only in games that use it)
    ACTION6 = "ACTION6"  # click x,y in 0-63 (reserved, unused in v1)
    ACTION7 = "ACTION7"  # undo (disabled in v1)


GameState = Literal["NOT_FINISHED", "WIN", "GAME_OVER"]


@dataclass(frozen=True)
class GameSpec:
    family: str = "gridworld"
    seed: int = 0
    n_levels: int = 6
    difficulty: int = 2            # 1..3
    rules: Optional[list[str]] = None  # None -> curriculum picks from the seed
    skin_shuffle: bool = True
    # A1, eval-v6: what the player sees, never the rules ("fog2,glimpse,recolor", engine generator/view.py).
    # Optional: games without a view omit the key in their spec dict, exactly as before.
    view: Optional[str] = None


class Truth(TypedDict):
    """Hidden from agents. Served by GET /sessions/{id}/truth and written into traces."""
    state: GameState
    level: int            # 1-based current level
    levels_total: int
    moves_used: int       # moves used on the current level attempt
    move_budget: int      # budget for the current level
    resets: int           # total resets in this game
    active_rules: list[str]
    new_rule: Optional[str]
    events: list[str]     # events produced by the last step, e.g. ["picked_key", "slid:4"]
    optimal_moves: int    # optimal solution length for the current level


class LevelInfo(TypedDict):
    level: int
    rules: list[str]
    new_rule: Optional[str]
    move_budget: int
    optimal_moves: int
    optimal_path: list[str]   # Action values, e.g. ["ACTION1", "ACTION4", ...]


class Description(TypedDict):
    """game.describe(). Contains the truth; UI and harness only, never shown to a model."""
    game_id: str          # "gridworld-s1234-d2-l6-<hash8>"
    spec: dict[str, Any]  # GameSpec as a dict
    engine_version: str
    levels_total: int
    levels: list[LevelInfo]
    available_actions: list[str]


class Game(Protocol):
    game_id: str

    def reset(self) -> Frame: ...
    def step(self, action: Action, x: Optional[int] = None, y: Optional[int] = None) -> Frame: ...
    def frame(self) -> Frame: ...           # current frame without acting
    def truth(self) -> Truth: ...
    def describe(self) -> Description: ...
    def available_actions(self) -> list[Action]: ...
    def clone(self) -> "Game": ...
    def state_hash(self) -> str: ...


def make_game(spec: GameSpec) -> Game:  # pragma: no cover - contract only
    raise NotImplementedError


def load_game(collection: str, game_id: str) -> Game:  # pragma: no cover - contract only
    """collection: path or name of a frozen collection file in data/collections/."""
    raise NotImplementedError


def list_games(collection: str) -> list[dict[str, Any]]:  # pragma: no cover - contract only
    """Metadata for every game in a collection: game_id, spec, levels_total, rules per level."""
    raise NotImplementedError


def render_png(frame: Frame, scale: int = 8) -> bytes:  # pragma: no cover - contract only
    raise NotImplementedError


def validate_frame(frame: Frame) -> None:
    """Raise ValueError unless frame matches the wire format."""
    if len(frame) != FRAME_SIZE:
        raise ValueError(f"frame has {len(frame)} rows, expected {FRAME_SIZE}")
    for i, row in enumerate(frame):
        if len(row) != FRAME_SIZE or any(c not in "0123456789abcdef" for c in row):
            raise ValueError(f"row {i} is not {FRAME_SIZE} lowercase hex chars")


if __name__ == "__main__":
    validate_frame(["0" * 64] * 64)
    print("engine_api contract ok")
