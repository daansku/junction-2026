"""Cell sprites: pixel masks for a cell of size c. Shapes stay readable at c >= 3."""
from __future__ import annotations

from functools import lru_cache

SPRITES = ("full", "ring", "dot", "cross", "x", "corners", "hbar", "vbar", "checker", "frame_dot",
           "arrow_up", "arrow_down", "arrow_left", "arrow_right", "bars", "diag")


@lru_cache(maxsize=None)
def mask(c: int, kind: str) -> tuple[tuple[int, int], ...]:
    if c < 3 or kind == "full":
        return tuple((x, y) for y in range(c) for x in range(c))
    lo, hi = c // 2 - (1 if c % 2 == 0 else 0), c // 2
    edge = lambda x, y: x in (0, c - 1) or y in (0, c - 1)  # noqa: E731
    tests = {
        "ring": edge,
        "dot": lambda x, y: c // 3 <= x < c - c // 3 and c // 3 <= y < c - c // 3,
        "cross": lambda x, y: lo <= x <= hi or lo <= y <= hi,
        "x": lambda x, y: x == y or x == c - 1 - y,
        "corners": lambda x, y: x in (0, c - 1) and y in (0, c - 1),
        "hbar": lambda x, y: lo <= y <= hi,
        "vbar": lambda x, y: lo <= x <= hi,
        "checker": lambda x, y: (x + y) % 2 == 0,
        "frame_dot": lambda x, y: edge(x, y) or (lo <= x <= hi and lo <= y <= hi),
        # arrows: shaft plus a cross-bar near the head
        "arrow_up": lambda x, y: lo <= x <= hi or y == 1,
        "arrow_down": lambda x, y: lo <= x <= hi or y == c - 2,
        "arrow_left": lambda x, y: lo <= y <= hi or x == 1,
        "arrow_right": lambda x, y: lo <= y <= hi or x == c - 2,
        "bars": lambda x, y: x % 2 == 0,
        "diag": lambda x, y: (x + y) % 3 == 0,
    }
    if kind not in tests:
        raise KeyError(kind)
    return tuple((x, y) for y in range(c) for x in range(c) if tests[kind](x, y))
