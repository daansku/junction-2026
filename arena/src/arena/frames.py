"""Frame helpers: 64x64 hex frames -> PNG bytes / text grid. No image library needed."""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

SIZE = 64

# Fallback palette until contracts/palette.json exists (A2 owns that file).
_DEFAULT_PALETTE = [
    "#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA", "#F012BE", "#FF851B",
    "#7FDBFF", "#870C25", "#FFFFFF", "#3D9970", "#B10DC9", "#01FF70", "#85144B", "#39CCCC",
]


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "PLAN.md").exists():
            return p
    return here.parents[3]


def _hex_to_rgb(c) -> tuple[int, int, int]:
    if isinstance(c, (list, tuple)):
        return tuple(int(x) for x in c[:3])  # type: ignore[return-value]
    if isinstance(c, dict):
        c = c.get("hex") or c.get("color") or c.get("rgb")
        return _hex_to_rgb(c)
    c = str(c).lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def load_palette() -> list[tuple[int, int, int]]:
    p = _repo_root() / "contracts" / "palette.json"
    try:
        data = json.loads(p.read_text())
        if isinstance(data, dict):
            data = data.get("colors") or data.get("palette") or [data[str(i)] for i in range(16)]
        pal = [_hex_to_rgb(c) for c in data]
        if len(pal) >= 16:
            return pal[:16]
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    return [_hex_to_rgb(c) for c in _DEFAULT_PALETTE]


def validate(frame: list[str]) -> None:
    if len(frame) != SIZE or any(len(r) != SIZE for r in frame):
        raise ValueError("frame must be 64 rows of 64 hex chars")
    int("".join(frame), 16)  # raises on non-hex


def to_png(frame: list[str], scale: int = 8, palette=None) -> bytes:
    """Indexed-colour PNG, each cell scale x scale pixels."""
    pal = palette or load_palette()
    raw = bytearray()
    for row in frame:
        line = bytearray([0])  # filter type 0
        for ch in row:
            line += bytes([int(ch, 16)]) * scale
        for _ in range(scale):
            raw += line
    w = h = SIZE * scale

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)
    plte = b"".join(bytes(c) for c in pal)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"PLTE", plte)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def to_text(frame: list[str]) -> str:
    """One hex char per cell, row 0 at the top. Same information as the image."""
    return "\n".join(frame)


def diff_count(a: list[str] | None, b: list[str]) -> int:
    if a is None:
        return SIZE * SIZE
    return sum(x != y for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def to_rle(frame: list[str]) -> str:
    """Lossless run-length text: each row as `colour x count` runs; identical consecutive rows merged.

        r0-1: 0x2 4x60 0x2
        r2: 0x64
    Same information as the full grid at a fraction of the tokens. Applied identically to every
    model that uses input mode "rle" (and stated on the dashboard), so it is fair perception.
    """
    def runs(row: str) -> str:
        out, cur, n = [], row[0], 0
        for ch in row:
            if ch == cur:
                n += 1
            else:
                out.append(f"{cur}x{n}")
                cur, n = ch, 1
        out.append(f"{cur}x{n}")
        return " ".join(out)

    lines, i = [], 0
    while i < len(frame):
        j = i
        while j + 1 < len(frame) and frame[j + 1] == frame[i]:
            j += 1
        tag = f"r{i}" if i == j else f"r{i}-{j}"
        lines.append(f"{tag}: {runs(frame[i])}")
        i = j + 1
    return "\n".join(lines)


def from_rle(text: str) -> list[str]:
    rows: list[str] = []
    for line in text.splitlines():
        tag, body = line.split(": ", 1)
        a, _, b = tag[1:].partition("-")
        row = "".join(c * int(n) for c, n in (r.split("x") for r in body.split()))
        rows += [row] * (int(b or a) - int(a) + 1)
    return rows
