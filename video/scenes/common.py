"""Shared look for every scene: colours, fonts, real-frame helpers.

Visual identity follows web/DESIGN.md and contracts/palette.json.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, ImageMobject, Rectangle, Square, Text, VGroup, config,
)
from manim.constants import RESAMPLING_ALGORITHMS
import manimpango

ROOT = pathlib.Path(__file__).resolve().parents[2]
VIDEO = ROOT / "video"
CACHE = VIDEO / "cache"

# ---- fonts (IBM Plex, OFL; converted from web/node_modules/@fontsource) ----
for _f in sorted((VIDEO / "assets" / "fonts").glob("*.ttf")):
    manimpango.register_font(str(_f))
SANS = "IBM Plex Sans"
MONO = "IBM Plex Mono"

# ---- DESIGN.md tokens (dark) ----
BG = "#0e0e0f"
SURFACE_1 = "#161617"
SURFACE_2 = "#1f1f21"
LINE = "#2c2c2f"
LINE_STRONG = "#3d3d42"
TEXT_1 = "#efefec"
TEXT_2 = "#a9a8a2"
TEXT_3 = "#76756f"
ACCENT = "#ffdc00"
GOOD = "#0ca30c"
BAD = "#d03b3b"

config.background_color = BG

# ---- game palette ----
_pal = json.loads((ROOT / "contracts" / "palette.json").read_text(encoding="utf-8"))
PALETTE = [c["hex"] for c in _pal["colors"]]
PALETTE_RGB = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in PALETTE], dtype=np.uint8)

# ---- failure modes: fixed colour per mode for the whole video (SCRIPT.md) ----
FAILURE_MODES = [
    # (rules.json mode, on-screen label, colour)
    ("no_effect_loop", "bumps walls, nothing changes", PALETTE[2]),
    ("late_reset", "resets too late", PALETTE[7]),
    ("belief_mismatch", "acts on a wrong belief", PALETTE[6]),
    ("unsolved_level", "never solves the level", PALETTE[5]),
    ("budget_exhaustion", "runs out of moves", PALETTE[4]),
    ("rule_blindness", "misses the new rule", PALETTE[8]),
]
MODE_COLOR = {m: c for m, _, c in FAILURE_MODES}


def load_json(rel: str):
    return json.loads((CACHE / rel).read_text(encoding="utf-8"))


def frame_array(frame: list[str]) -> np.ndarray:
    """64 hex strings -> (64, 64) int array of palette indices."""
    return np.array([[int(ch, 16) for ch in row] for row in frame], dtype=np.uint8)


def frame_image(frame: list[str] | np.ndarray, height: float = 4.0) -> ImageMobject:
    """Crisp frame as an image (fast; use for anything that does not morph cell by cell)."""
    a = frame if isinstance(frame, np.ndarray) else frame_array(frame)
    rgb = PALETTE_RGB[a]
    img = ImageMobject(rgb)
    img.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    img.height = height
    return img


def set_frame(img: ImageMobject, frame: list[str] | np.ndarray) -> None:
    """Swap the pixels of a frame image in place (for replays)."""
    a = frame if isinstance(frame, np.ndarray) else frame_array(frame)
    rgba = np.concatenate([PALETTE_RGB[a], np.full(a.shape + (1,), 255, dtype=np.uint8)], axis=2)
    img.pixel_array = rgba


def frame_cells(frame: list[str] | np.ndarray, size: float = 4.0, skip_bg: bool = True) -> VGroup:
    """Frame as individual squares (slow; use when cells must move or morph)."""
    a = frame if isinstance(frame, np.ndarray) else frame_array(frame)
    n = a.shape[0]
    s = size / n
    cells = VGroup()
    for r in range(n):
        for c in range(a.shape[1]):
            v = int(a[r, c])
            if skip_bg and v == 0:
                continue
            sq = Square(side_length=s, stroke_width=0, fill_color=PALETTE[v], fill_opacity=1)
            sq.move_to([(c - (n - 1) / 2) * s, ((n - 1) / 2 - r) * s, 0])
            cells.add(sq)
    return cells


def framed(mob, buff: float = 0.0) -> VGroup:
    """Hairline border around a frame, as on the web app."""
    border = Rectangle(width=mob.width + 2 * buff, height=mob.height + 2 * buff,
                       stroke_color=LINE_STRONG, stroke_width=2, fill_opacity=0).move_to(mob)
    return border


def label(text: str, size: float = 28, color: str = TEXT_1, mono: bool = False, weight: str = "NORMAL") -> Text:
    return Text(text, font=MONO if mono else SANS, font_size=size, color=color, weight=weight)


def kicker(text: str, size: float = 20) -> Text:
    """Uppercase mono section label (DESIGN.md 'kicker')."""
    return Text(text.upper(), font=MONO, font_size=size, color=TEXT_2)


def agent_sprite(color: str = PALETTE[15], unit: float = 0.22) -> VGroup:
    """A small block-figure agent made of palette cells (5x5, original design)."""
    pattern = [
        ".###.",
        "#o#o#",
        "#####",
        ".#.#.",
        "##.##",
    ]
    g = VGroup()
    for r, row in enumerate(pattern):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            fill = PALETTE[10] if ch == "o" else color
            sq = Square(side_length=unit, stroke_width=0, fill_color=fill, fill_opacity=1)
            sq.move_to([(c - 2) * unit, (2 - r) * unit, 0])
            g.add(sq)
    return g


PLACEHOLDER = "#ff4fd8"  # loud colour reserved for unlocked numbers (see NUMBERS.md)


def placeholder_tag(mob, text: str = "PLACEHOLDER") -> Text:
    return Text(text, font=MONO, font_size=14, color=PLACEHOLDER).next_to(mob, UP, buff=0.05)


def pad_to_narration(scene, key: str, tail: float = 0.0, extra: float = 0.6) -> None:
    """Wait until the scene is at least as long as its narration (cache/audio/durations.json).
    `tail` = seconds of animation still to come after this call (e.g. a final fade)."""
    p = CACHE / "audio" / "durations.json"
    if not p.exists():
        return
    target = json.loads(p.read_text(encoding="utf-8")).get(key)
    if target is None:
        return
    now = scene.renderer.time
    missing = target + extra - tail - now
    if missing > 0.05:
        scene.wait(missing)
