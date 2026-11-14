"""Dependency-free PNG writer for frames and contact sheets."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .palette import load_palette


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_png(pixels: list[list[int]], scale: int = 8, palette=None) -> bytes:
    pal = palette or load_palette()
    h, w = len(pixels), len(pixels[0])
    raw = bytearray()
    for row in pixels:
        line = bytearray()
        for v in row:
            line += bytes(pal[v]) * scale
        for _ in range(scale):
            raw += b"\x00" + line
    ihdr = struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))


def frame_pixels(frame: list[str]) -> list[list[int]]:
    return [[int(ch, 16) for ch in row] for row in frame]


def frame_png(frame: list[str], scale: int = 8) -> bytes:
    return encode_png(frame_pixels(frame), scale)


def contact_sheet(frames: list[list[str]], cols: int = 3, gap: int = 2, scale: int = 4,
                  gap_color: int = 11) -> bytes:
    """Grid of frames for decks and quick review."""
    rows = (len(frames) + cols - 1) // cols
    W, H = cols * 64 + (cols + 1) * gap, rows * 64 + (rows + 1) * gap
    px = [[gap_color] * W for _ in range(H)]
    for i, fr in enumerate(frames):
        ox, oy = gap + (i % cols) * (64 + gap), gap + (i // cols) * (64 + gap)
        for y, row in enumerate(frame_pixels(fr)):
            px[oy + y][ox:ox + 64] = row
    return encode_png(px, scale)


def write_png(path: str | Path, data: bytes) -> None:
    Path(path).write_bytes(data)
