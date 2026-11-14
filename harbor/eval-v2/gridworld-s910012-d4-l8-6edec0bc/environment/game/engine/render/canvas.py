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
        self.rot = 0
        self.lw = self.lh = 1

    def set_grid(self, w: int, h: int, rot: int = 0, stable: bool = False) -> None:
        """Logical grid w x h, shown rotated `rot` quarter turns clockwise. `stable` keeps the
        cell size the same in every orientation (levels that can rotate)."""
        self.lw, self.lh, self.rot = w, h, rot % 4
        sw, sh = (h, w) if self.rot % 2 else (w, h)
        self.cs = max(1, min(SIZE // sw, PLAY_H // sh))
        if stable:
            self.cs = max(1, min(self.cs, SIZE // sh, PLAY_H // sw))
        self.ox = (SIZE - sw * self.cs) // 2
        self.oy = HUD_ROWS + (PLAY_H - sh * self.cs) // 2

    def _xf(self, x: int, y: int, w: int, h: int) -> tuple[int, int]:
        """Rotate (x, y) in a w x h box `rot` times clockwise."""
        for _ in range(self.rot):
            x, y, w, h = h - 1 - y, x, h, w
        return x, y

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
        sx, sy = self._xf(p[0], p[1], self.lw, self.lh)
        bx, by = self.ox + sx * self.cs, self.oy + sy * self.cs
        cs = self.cs
        for dx, dy in mask(cs, spr):
            if self.rot:
                dx, dy = self._xf(dx, dy, cs, cs)
            self.put(bx + dx, by + dy, col)

    def to_hex(self) -> list[str]:
        """64 strings of 64 hex chars, one char per pixel (§4.1)."""
        return [bytes(row).translate(_HEX).decode("ascii") for row in self.px]


_HEX = bytes(b"0123456789abcdef"[i & 15] for i in range(256))
