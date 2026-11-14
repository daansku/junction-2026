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


class Narration:
    """Ties voice-over lines to the animation.

    Call `cue(i)` where the visual beat for line i starts. The line then starts there (plus a
    short delay), unless line i-1 is still being spoken, in which case the scene holds until it
    ends. `finish()` holds until the last line ends and writes cache/audio/<key>.cues.json
    (start time of every line in scene seconds), which tools/build.py uses to place each line's
    audio and caption. Line lengths come from cache/audio/<key>.lines.json (tools/tts.py).
    """

    GAP = 0.35          # minimum silence between two lines

    def __init__(self, scene, key: str):
        self.scene, self.key = scene, key
        p = CACHE / "audio" / f"{key}.lines.json"
        self.lines = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        self.free_at = 0.0
        self.starts: list[float] = []

    def dur(self, i: int, default: float = 3.0) -> float:
        return self.lines[i]["dur"] if i < len(self.lines) else default

    def cue(self, i: int, delay: float = 0.25) -> None:
        if i != len(self.starts):
            raise ValueError(f"{self.key}: cue({i}) out of order, expected cue({len(self.starts)})")
        hold = self.free_at - (self.scene.renderer.time + delay)
        if hold > 0.07:
            self.scene.wait(hold)
        start = max(self.scene.renderer.time + delay, self.free_at)
        self.starts.append(round(start, 3))
        self.free_at = start + self.dur(i) + self.GAP

    def finish(self, tail: float = 0.0, extra: float = 0.6) -> None:
        """`tail` = seconds of animation still to come after this call (e.g. a final fade)."""
        while len(self.starts) < len(self.lines):
            self.cue(len(self.starts), delay=0.0)
        missing = self.free_at - self.GAP + extra - tail - self.scene.renderer.time
        if missing > 0.05:
            self.scene.wait(missing)
        out = CACHE / "audio" / f"{self.key}.cues.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"starts": self.starts}), encoding="utf-8")
