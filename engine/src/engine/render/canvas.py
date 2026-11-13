"""64x64 index canvas plus the cell -> pixel mapping for the play area.

Layout (PLAN.md §4.1):
  rows 0-1   move-budget bar (remaining moves, full width = full budget)
  rows 3-4   level pips (left) and component HUD items (right of the pips)
  rows 6-63  play area: logical grid scaled by an integer cell size, centred
"""
from __future__ import annotations

from .sprites import mask

SIZE = 64
HUD_ROWS = 6
PLAY_H = SIZE - HUD_ROWS


class Canvas:
    def __init__(self, skin: dict[str, tuple[int, str]], fill: int = 0):
        self.px = [bytearray([fill]) * SIZE for _ in range(SIZE)]
        self.skin = skin
        self.cs = 1
        self.ox = 0
        self.oy = HUD_ROWS

    def set_grid(self, w: int, h: int) -> None:
        self.cs = max(1, min(SIZE // w, PLAY_H // h))
        self.ox = (SIZE - w * self.cs) // 2
        self.oy = HUD_ROWS + (PLAY_H - h * self.cs) // 2

    def put(self, x: int, y: int, color: int) -> None:
        if 0 <= x < SIZE and 0 <= y < SIZE:
            self.px[y][x] = color

    def rect(self, x: int, y: int, w: int, h: int, color: int) -> None:
        for yy in range(max(0, y), min(SIZE, y + h)):
            row = self.px[yy]
            for xx in range(max(0, x), min(SIZE, x + w)):
                row[xx] = color

    def color(self, role: str) -> int:
        return self.skin[role][0]

    def cell(self, p: tuple[int, int], role: str, sprite: str | None = None,
             color: int | None = None) -> None:
        col, spr = self.skin[role]
        if sprite is not None:
            spr = sprite
        if color is not None:
            col = color
        bx, by = self.ox + p[0] * self.cs, self.oy + p[1] * self.cs
        for dx, dy in mask(self.cs, spr):
            self.put(bx + dx, by + dy, col)

    def to_hex(self) -> list[str]:
        """64 strings of 64 hex chars, one char per pixel (§4.1)."""
        return [bytes(row).translate(_HEX).decode("ascii") for row in self.px]


_HEX = bytes(b"0123456789abcdef"[i & 15] for i in range(256))
