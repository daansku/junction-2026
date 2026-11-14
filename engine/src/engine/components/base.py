"""Component plugin interface. One file per component in this package.

A component is stateless code; static data lives in `level.data[name]`, dynamic data in
`state.c[name]`. Hooks mutate the *copied* state they are given (the core copies before step).
Every hook has a no-op default, so a component overrides only what it needs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.level import Level, Pos, State
    from ..generator.placement import Draft
    from ..render.canvas import Canvas


def cells(level: "Level", name: str, key: str) -> list[tuple[int, int]]:
    """Static cell list from level.data[name][key] as tuples."""
    return [tuple(p[:2]) for p in level.data.get(name, {}).get(key, [])]


def static(level: "Level", name: str, build):
    """Per-level cache of parsed static data (hot path for the solver). Not a dataclass
    field, so dataclasses.replace() gives a fresh cache and to_dict() ignores it."""
    cache = level.__dict__.setdefault("_cache", {})
    if name not in cache:
        cache[name] = build(level.data.get(name, {}))
    return cache[name]


class Component:
    name: str = ""
    tier: int = 0
    always_on: bool = False   # tier-0 parts (walls, goal, budget) are active in every level
    layer: int = 50           # draw order, low first; player is drawn at 100
    uses_interact: bool = False
    roles: dict[str, tuple[int, str]] = {}  # skin role -> default (colour index, sprite)

    # --- generation ---
    place_order: int = 50     # lower places first (teleporters cut the map before doors use it)

    def place(self, draft: "Draft") -> bool:
        """Add this component to a draft level (walls, draft.data[name], draft.claim(cell)).
        Return False if the layout does not suit it; the generator then retries."""
        return True

    # --- lifecycle ---
    def init_state(self, level: "Level", state: "State") -> None: ...

    def blocks_object(self, level: "Level", state: "State", pos: "Pos") -> bool:
        """True if a pushed object may not enter `pos`."""
        return False

    # --- movement ---
    def remap(self, level: "Level", state: "State", action: Any) -> Any:
        return action

    def on_action(self, level: "Level", state: "State", action: Any, events: list[str]) -> None:
        """Called with the final (remapped) action before the player moves (twins, enemies)."""

    def blocks(self, level: "Level", state: "State", pos: "Pos", d: tuple[int, int]) -> bool:
        """True if the player may not enter `pos` moving in direction `d`."""
        return False

    def push(self, level: "Level", state: "State", pos: "Pos", d: tuple[int, int],
             events: list[str]) -> bool | None:
        """Called before entering `pos`. None = nothing here; True = pushed ok; False = blocked."""
        return None

    def on_enter(self, level: "Level", state: "State", pos: "Pos", d: tuple[int, int],
                 events: list[str]) -> None: ...

    def slide(self, level: "Level", state: "State", pos: "Pos", d: tuple[int, int]) -> bool:
        """True if the player keeps moving in `d` after entering `pos` (ice)."""
        return False

    def interact(self, level: "Level", state: "State", events: list[str]) -> None: ...

    def on_step(self, level: "Level", state: "State", events: list[str]) -> None:
        """After every counted action (move attempt or interact)."""

    # --- outcome ---
    def win_ok(self, level: "Level", state: "State") -> bool:
        """All active components must agree before standing on the goal wins."""
        return True

    def lost(self, level: "Level", state: "State") -> bool:
        return False

    # --- drawing ---
    def draw(self, level: "Level", state: "State", cv: "Canvas") -> None: ...

    def hud(self, level: "Level", state: "State") -> list[tuple[str, int, int]]:
        """HUD items: (role, value, max). Drawn as pip rows in the HUD strip."""
        return []
