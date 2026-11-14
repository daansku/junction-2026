"""Palette for PNG export only (frames carry indices). contracts/palette.json wins when present."""
from __future__ import annotations

import json
from pathlib import Path

# copy of contracts/palette.json v1, used when the engine is installed outside the repo
FALLBACK = [
    "#000000", "#1E5BD8", "#E5383B", "#2FB54A", "#F5C518", "#8A8F98", "#D63AAF", "#F2832B",
    "#6FD3F2", "#7A1F2B", "#FFFFFF", "#3A3F47", "#8E5CE6", "#1FA39A", "#A8D94A", "#8B5A2B",
]


def _find_contract() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        p = parent / "contracts" / "palette.json"
        if p.exists():
            return p
    return None


def _to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def load_palette() -> list[tuple[int, int, int]]:
    p = _find_contract()
    hexes = FALLBACK
    if p is not None:
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw = raw.get("colors") or raw.get("palette") or [raw[str(i)] for i in range(16)]
            items = [x["hex"] if isinstance(x, dict) else x for x in raw]
            if len(items) >= 16:
                hexes = items[:16]
        except Exception:
            pass
    return [_to_rgb(h) for h in hexes]
