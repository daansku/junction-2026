"""Frame -> PNG and frame -> text grid, using contracts/palette.json."""
from __future__ import annotations

import io
import json
from functools import lru_cache

from .config import REPO_ROOT


@lru_cache(maxsize=1)
def palette_rgb() -> list[tuple[int, int, int]]:
    data = json.loads((REPO_ROOT / "contracts" / "palette.json").read_text(encoding="utf-8"))
    out = []
    for c in sorted(data["colors"], key=lambda c: c["index"]):
        h = c["hex"].lstrip("#")
        out.append((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))
    return out


def frame_to_png(frame: list[str], scale: int = 8) -> bytes:
    from PIL import Image

    pal = palette_rgb()
    h, w = len(frame), len(frame[0]) if frame else 0
    img = Image.new("RGB", (w, h))
    img.putdata([pal[int(ch, 16)] for row in frame for ch in row])
    if scale > 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def frame_to_text(frame: list[str]) -> str:
    """Text grid for models: one row per line, one hex char per cell (0-f)."""
    return "\n".join(frame)
