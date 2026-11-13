"""Cell sprites: pixel masks for a cell of size c. Shapes stay readable at c >= 3."""
from __future__ import annotations

from functools import lru_cache

SPRITES = ("full", "ring", "dot", "cross", "x", "corners", "hbar", "vbar", "checker", "frame_dot")


@lru_cache(maxsize=None)
def mask(c: int, kind: str) -> tuple[tuple[int, int], ...]:
    if c < 3 or kind == "full":
        return tuple((x, y) for y in range(c) for x in range(c))
    lo, hi = c // 2 - (1 if c % 2 == 0 else 0), c // 2
    edge = lambda x, y: x in (0, c - 1) or y in (0, c - 1)  # noqa: E731
    tests = {
        "ring": edge,
        "dot": lambda x, y: 0 < x < c - 1 and 0 < y < c - 1,
        "cross": lambda x, y: lo <= x <= hi or lo <= y <= hi,
        "x": lambda x, y: x == y or x == c - 1 - y,
        "corners": lambda x, y: x in (0, c - 1) and y in (0, c - 1),
        "hbar": lambda x, y: lo <= y <= hi,
        "vbar": lambda x, y: lo <= x <= hi,
        "checker": lambda x, y: (x + y) % 2 == 0,
        "frame_dot": lambda x, y: edge(x, y) or (lo <= x <= hi and lo <= y <= hi),
    }
    if kind not in tests:
        raise KeyError(kind)
    return tuple((x, y) for y in range(c) for x in range(c) if tests[kind](x, y))
