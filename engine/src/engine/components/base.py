"""Component plugin interface. One file per component in this package.

A component is stateless code; static data lives in `level.data[name]`, dynamic data in
`state.c[name]`. Hooks mutate the *copied* state they are given (the core copies before step).
Every hook has a no-op default, so a component overrides only what it needs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.level import Level, Pos, State
    from ..render.canvas import Canvas


class Component:
    name: str = ""
    tier: int = 0
    always_on: bool = False   # tier-0 parts (walls, goal, budget) are active in every level
    layer: int = 50           # draw order, low first; player is drawn at 100
    uses_interact: bool = False
    roles: dict[str, tuple[int, str]] = {}  # skin role -> default (colour index, sprite)

    # --- lifecycle ---
    def init_state(self, level: "Level", state: "State") -> None: ...

    # --- movement ---
    def remap(self, level: "Level", state: "State", action: Any) -> Any:
        return action

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
