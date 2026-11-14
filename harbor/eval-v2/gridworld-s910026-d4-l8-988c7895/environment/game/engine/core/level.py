"""Level (static layout, JSON-serialisable) and State (dynamic, hashable)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

Pos = tuple[int, int]


@dataclass
class Level:
    w: int
    h: int
    walls: frozenset[Pos]
    start: Pos
    goal: Pos
    rules: tuple[str, ...] = ()          # active non-tier-0 components
    new_rule: str | None = None          # the rule this level introduces (None on level 1)
    data: dict[str, Any] = field(default_factory=dict)  # static per-component data, JSON-able
    move_budget: int = 0                 # 0 = unlimited (used while solving)
    optimal_moves: int = 0
    optimal_path: list[str] = field(default_factory=list)

    def in_bounds(self, p: Pos) -> bool:
        return 0 <= p[0] < self.w and 0 <= p[1] < self.h

    # ---- serialisation -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        rows = []
        for y in range(self.h):
            rows.append("".join("#" if (x, y) in self.walls else "." for x in range(self.w)))
        return {
            "w": self.w, "h": self.h, "rows": rows,
            "start": list(self.start), "goal": list(self.goal),
            "rules": list(self.rules), "new_rule": self.new_rule,
            "data": self.data,
            "move_budget": self.move_budget, "optimal_moves": self.optimal_moves,
            "optimal_path": list(self.optimal_path),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Level":
        walls = frozenset(
            (x, y) for y, row in enumerate(d["rows"]) for x, ch in enumerate(row) if ch == "#"
        )
        return cls(
            w=d["w"], h=d["h"], walls=walls,
            start=tuple(d["start"]), goal=tuple(d["goal"]),
            rules=tuple(d.get("rules", ())), new_rule=d.get("new_rule"),
            data=d.get("data", {}),
            move_budget=d.get("move_budget", 0), optimal_moves=d.get("optimal_moves", 0),
            optimal_path=list(d.get("optimal_path", [])),
        )


def canon(v: Any) -> Any:
    """Canonical, order-stable form of a state value (sets sorted) for stable hashing."""
    if isinstance(v, (set, frozenset)):
        return sorted((canon(x) for x in v), key=repr)
    if isinstance(v, (tuple, list)):
        return [canon(x) for x in v]
    if isinstance(v, dict):
        return {str(k): canon(v[k]) for k in sorted(v, key=str)}
    return v


class State:
    """Dynamic level state. Component state lives in `c[name]` and must be immutable/hashable
    (int, str, tuple, frozenset). Copy before mutating: `s2 = s.copy()`."""

    __slots__ = ("pos", "moves", "c")

    def __init__(self, pos: Pos, moves: int = 0, c: dict[str, Any] | None = None):
        self.pos = pos
        self.moves = moves
        self.c: dict[str, Any] = c if c is not None else {}

    def copy(self) -> "State":
        return State(self.pos, self.moves, dict(self.c))

    def key(self) -> tuple:
        """Solver key: everything except the move counter."""
        return (self.pos, tuple(sorted(self.c.items())))

    def canonical(self) -> str:
        return json.dumps({"pos": list(self.pos), "moves": self.moves, "c": canon(self.c)},
                          sort_keys=True, separators=(",", ":"))
