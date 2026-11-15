"""S6 Business value (placeholder until docs/BUSINESS.md exists) and S7 Close
(broken agent reassembles, pixel wordmark "Game Factory"). See SCRIPT.md.
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
    Narration,
    ACCENT, CACHE, FAILURE_MODES, GOOD, MONO, PALETTE, PLACEHOLDER, ROOT, SANS, TEXT_1, TEXT_2,
    TEXT_3, agent_sprite, frame_image, load_json, set_frame,
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
    "training environments for labs: unlimited levels with a proven optimal run",
    "private evals that can't leak: a fresh, verified game set for every evaluation",
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
        vo = Narration(self, "S6S7")
        vo.cue(0, delay=0.2)
        self.play(FadeIn(head), run_time=0.4)
        self.add(tag)
        self.play(LaggedStart(*[FadeIn(i, shift=RIGHT * 0.2) for i in items], lag_ratio=0.4), run_time=1.4)
        self.wait(2.6)
        vo.cue(1, delay=0.6)
        self.play(FadeOut(VGroup(head, items, tag)), run_time=0.5)

        # ---------------- S7 callback to the opening: the broken agent puts itself back together ----
        agent = agent_sprite(FAILURE_MODES[0][2], unit=0.3)
        cx = agent.get_x()
        left = VGroup(*[p for p in agent if p.get_x() < cx])
        right = VGroup(*[p for p in agent if p.get_x() >= cx])
        left.shift(LEFT * 0.5 + DOWN * 0.15).rotate(0.35)
        right.shift(RIGHT * 0.15 + UP * 0.1).rotate(-0.5)
        self.play(FadeIn(left), FadeIn(right), run_time=0.5)
        self.play(left.animate.rotate(-0.35).shift(RIGHT * 0.5 + UP * 0.15),
                  right.animate.rotate(0.5).shift(LEFT * 0.15 + DOWN * 0.1), run_time=0.9,
                  rate_func=rate_functions.ease_in_out_cubic)
        whole = VGroup(left, right)
        self.play(whole.animate.set_fill(GOOD), run_time=0.5)
        self.wait(0.8)

        # ---------------- wordmark ----------------
        word = wordmark("Game Factory", unit=0.14).move_to(ORIGIN)
        self.play(FadeOut(whole), run_time=0.5)
        vo.cue(2, delay=0.3)
        self.play(LaggedStart(*[FadeIn(s, scale=0.3) for s in word], lag_ratio=0.004, run_time=1.4))
        self.wait(2.0)
        vo.finish(extra=1.0)
