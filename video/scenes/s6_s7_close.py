"""S6 Business value (placeholder until docs/BUSINESS.md exists) and S7 Close
(callback grid, pixel wordmark 'Game Factory', URL, QR code to /challenge). See SCRIPT.md.
"""
from __future__ import annotations

import random

import numpy as np
import qrcode
from manim import (
    DOWN, LEFT, ORIGIN, RIGHT, UP, FadeIn, FadeOut, Group, LaggedStart, Rectangle, Scene, Square,
    Text, VGroup, rate_functions,
)

from common import (
    ACCENT, CACHE, FAILURE_MODES, GOOD, MONO, PALETTE, PLACEHOLDER, ROOT, SANS, TEXT_1, TEXT_2,
    TEXT_3, frame_image, load_json, set_frame,
)

random.seed(3)
URL = (ROOT / "coordination" / "API_URL").read_text().strip().rstrip("/") + "/challenge"

# 5x5 pixel letters for the wordmark (original glyphs)
GLYPHS = {
    "G": [".###.", "#....", "#.###", "#...#", ".###."],
    "A": [".###.", "#...#", "#####", "#...#", "#...#"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    "E": ["#####", "#....", "####.", "#....", "#####"],
    "F": ["#####", "#....", "####.", "#....", "#...."],
    "C": [".####", "#....", "#....", "#....", ".####"],
    "T": ["#####", "..#..", "..#..", "..#..", "..#.."],
    "O": [".###.", "#...#", "#...#", "#...#", ".###."],
    "R": ["####.", "#...#", "####.", "#..#.", "#...#"],
    "Y": ["#...#", ".#.#.", "..#..", "..#..", "..#.."],
    " ": [".....", ".....", ".....", ".....", "....."],
}
WORD_COLORS = [PALETTE[i] for i in (1, 2, 3, 4, 6, 7, 8, 13, 14, 12)]

BUSINESS = [  # PLACEHOLDER until docs/BUSINESS.md (A5) picks the ideas
    "private evals that can't leak: a fresh, verified game set for every evaluation",
    "training environments for labs: unlimited levels with a proven optimal run",
]


def wordmark(text: str, unit: float = 0.12) -> VGroup:
    g = VGroup()
    x = 0
    ci = 0
    for ch in text.upper():
        rows = GLYPHS[ch]
        color = WORD_COLORS[ci % len(WORD_COLORS)]
        if ch != " ":
            ci += 1
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                if v == "#":
                    sq = Square(side_length=unit * 0.94, stroke_width=0, fill_color=color, fill_opacity=1)
                    sq.move_to([(x + c) * unit, -r * unit, 0])
                    g.add(sq)
        x += 6
    return g.move_to(ORIGIN)


def qr_mob(data: str, size: float = 2.2) -> VGroup:
    q = qrcode.QRCode(border=2)
    q.add_data(data)
    q.make()
    m = np.array(q.get_matrix(), dtype=bool)
    n = m.shape[0]
    s = size / n
    g = VGroup(Rectangle(width=size, height=size, fill_color="#ffffff", fill_opacity=1, stroke_width=0))
    for r in range(n):
        for c in range(n):
            if m[r, c]:
                g.add(Square(side_length=s, stroke_width=0, fill_color="#000000", fill_opacity=1)
                      .move_to([(c - (n - 1) / 2) * s, ((n - 1) / 2 - r) * s, 0]))
    return g


class S6S7Close(Scene):
    def construct(self):
        # ---------------- S6 business value ----------------
        head = Text("why it matters beyond the hackathon", font=MONO, font_size=20, color=TEXT_2).to_edge(UP, buff=1.0)
        items = VGroup()
        for i, line in enumerate(BUSINESS):
            sw = Square(side_length=0.3, stroke_width=0, fill_color=[PALETTE[13], PALETTE[4]][i], fill_opacity=1)
            t = Text(line, font=SANS, font_size=26, color=TEXT_1)
            items.add(VGroup(sw, t).arrange(RIGHT, buff=0.3))
        items.arrange(DOWN, aligned_edge=LEFT, buff=0.6).move_to(ORIGIN)
        if items.width > 13:
            items.scale_to_fit_width(13)
        tag = Text("PLACEHOLDER: waiting for docs/BUSINESS.md", font=MONO, font_size=16, color=PLACEHOLDER).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(head), run_time=0.4)
        self.add(tag)
        self.play(LaggedStart(*[FadeIn(i, shift=RIGHT * 0.2) for i in items], lag_ratio=0.4), run_time=1.4)
        self.wait(2.6)
        self.play(FadeOut(VGroup(head, items, tag)), run_time=0.5)

        # ---------------- S7 callback grid: a few agents reach the goal ----------------
        srcs = [load_json(f"wall/{p.name}") for p in sorted((CACHE / "wall").glob("*.json"))]
        cols, rows = 16, 9
        th, gap = 0.72, 0.1
        tiles = Group()
        for r in range(rows):
            for c in range(cols):
                src = srcs[(r * cols + c + 11) % len(srcs)]
                t = frame_image(src["frames"][random.randrange(len(src["frames"]))]["frame"], height=th)
                t.move_to([(c - (cols - 1) / 2) * (th + gap), ((rows - 1) / 2 - r) * (th + gap), 0])
                t.frames = [f["frame"] for f in src["frames"]]
                t.phase = random.random() * 20
                tiles.add(t)
        clock = {"t": 0.0}

        def tick(m, dt):
            clock["t"] += dt
            for t in m:
                set_frame(t, t.frames[int(t.phase + clock["t"] * 6) % len(t.frames)])

        tiles.add_updater(tick)
        self.play(FadeIn(tiles), run_time=0.8)
        winners = random.sample(range(len(tiles)), 14)
        glows = [Rectangle(width=th, height=th, stroke_color=GOOD, stroke_width=5, fill_color=GOOD, fill_opacity=0.0).move_to(tiles[i])
                 for i in winners]
        self.play(LaggedStart(*[FadeIn(g, scale=1.2) for g in glows], lag_ratio=0.12), run_time=1.8)
        self.wait(0.6)
        tiles.clear_updaters()

        # ---------------- wordmark, URL, QR ----------------
        word = wordmark("Game Factory", unit=0.14).move_to(UP * 1.6 + LEFT * 1.8)
        line = Text("Try to beat the AI yourself.", font=SANS, font_size=34, color=TEXT_1).next_to(word, DOWN, buff=0.6).align_to(word, LEFT)
        url = Text(URL.replace("https://", ""), font=MONO, font_size=18, color=ACCENT).next_to(line, DOWN, buff=0.3).align_to(word, LEFT)
        qr = qr_mob(URL, size=2.6).to_edge(RIGHT, buff=1.0).shift(DOWN * 0.2)
        self.play(FadeOut(Group(tiles, *glows)), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(s, scale=0.3) for s in word], lag_ratio=0.004, run_time=1.4))
        self.play(FadeIn(line, shift=UP * 0.1), run_time=0.5)
        self.play(FadeIn(url), FadeIn(qr), run_time=0.6)
        self.wait(3.0)
