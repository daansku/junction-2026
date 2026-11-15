"""S5 Post-training: base vs trained on our games (no control run: no time, Anssi Sat night) on the outside-benchmark suite, with 95% CIs.
See SCRIPT.md S5 and bench/PROTOCOL.md.

PLACEHOLDER until the 07:00 lock: values below are invented layout values, drawn in the
placeholder colour and listed in NUMBERS.md. Replace with data/derived/bench/<run>/summary.json.
"""
from __future__ import annotations

import random

from manim import (
    Group,
    DOWN, LEFT, RIGHT, UP, FadeIn, FadeOut, GrowFromEdge, LaggedStart, Line, Rectangle, Scene,
    Square, Text, VGroup, rate_functions,
)

from common import (
    Narration,
    FAILURE_MODES, LINE_STRONG, MONO, PALETTE, PLACEHOLDER, SANS, TEXT_1, TEXT_2, TEXT_3,
    agent_sprite,
)

random.seed(5)
# (row, label, mean, ci_low, ci_high): PLACEHOLDER layout values, NOT results
ROWS = [
    ("base", "Qwen3.5-9B base", 0.60, 0.58, 0.62),
    ("ours", "trained on our games", 0.63, 0.61, 0.65),
]
PLACEHOLDER_DATA = True


class S5PostTrain(Scene):
    def construct(self):
        # ---- failure colours flow into one small agent ----
        bot = agent_sprite(PALETTE[15], unit=0.3)
        name = Text("Qwen3.5-9B", font=MONO, font_size=22, color=TEXT_2).next_to(bot, DOWN, buff=0.3)
        bits = VGroup()
        for _ in range(90):
            c = random.choice([c for _, _, c in FAILURE_MODES])
            sq = Square(side_length=0.12, stroke_width=0, fill_color=c, fill_opacity=1)
            sq.move_to([random.uniform(-7, 7), random.choice([-1, 1]) * random.uniform(2.5, 4), 0])
            bits.add(sq)
        vo = Narration(self, "S5")
        vo.cue(0, delay=0.2)
        self.play(FadeIn(bot), FadeIn(name), FadeIn(bits), run_time=0.6)
        self.play(LaggedStart(*[b.animate.move_to(bot.get_center()).scale(0.2).set_opacity(0) for b in bits],
                              lag_ratio=0.01, run_time=1.8, rate_func=rate_functions.ease_in_cubic))
        q = Text("can a small model learn from our games?", font=SANS, font_size=26, color=TEXT_1).to_edge(UP, buff=0.8)
        self.play(FadeIn(q), run_time=0.4)
        self.wait(1.0)
        vo.cue(1, delay=0.4)
        self.play(FadeOut(VGroup(bot, name, bits)), q.animate.scale(0.75).to_edge(UP, buff=0.4), run_time=0.6)

        # ---- three bars with 95% CIs ----
        sub = Text("mean accuracy, outside reasoning benchmarks (BBH, MATH, GSM8K, MedQA, MMLU-Pro) · 95% CI",
                   font=MONO, font_size=14, color=TEXT_3).next_to(q, DOWN, buff=0.2)
        lo, hi = 0.5, 0.7             # visible axis range
        width = 7.0
        x0 = -2.0

        def x(v):
            return x0 + (v - lo) / (hi - lo) * width

        g = VGroup()
        bars, cis = [], []
        y = 1.0
        for key, label, m, a, b in ROWS:
            lab = Text(label, font=SANS, font_size=18, color=TEXT_1 if key == "ours" else TEXT_2)
            lab.move_to([x0 - 0.3 - lab.width / 2, y, 0])
            color = "#3987e5" if key != "ours" else "#199e70"
            bar = Rectangle(width=x(m) - x0, height=0.42, fill_color=color, fill_opacity=1, stroke_width=0)
            bar.move_to([x0 + bar.width / 2, y, 0])
            ci = VGroup(Line([x(a), y, 0], [x(b), y, 0], stroke_color=TEXT_1, stroke_width=3),
                        Line([x(a), y - 0.12, 0], [x(a), y + 0.12, 0], stroke_color=TEXT_1, stroke_width=3),
                        Line([x(b), y - 0.12, 0], [x(b), y + 0.12, 0], stroke_color=TEXT_1, stroke_width=3))
            num = Text(f"{m:.3f}", font=MONO, font_size=16, color=PLACEHOLDER if PLACEHOLDER_DATA else TEXT_1)
            num.next_to(ci, RIGHT, buff=0.15)
            g.add(lab)
            bars.append(bar)
            cis.append(VGroup(ci, num))
            y -= 1.0
        axis = Line([x0, 1.5, 0], [x0, y + 0.5, 0], stroke_color=LINE_STRONG, stroke_width=1)
        self.play(FadeIn(sub), FadeIn(g), FadeIn(axis), run_time=0.5)
        self.play(LaggedStart(*[GrowFromEdge(b, LEFT) for b in bars], lag_ratio=0.2, run_time=1.4))
        self.play(LaggedStart(*[FadeIn(c) for c in cis], lag_ratio=0.2, run_time=0.8))
        if PLACEHOLDER_DATA:
            tag = Text("PLACEHOLDER: post-training result not in yet", font=MONO, font_size=18, color=PLACEHOLDER)
            tag.to_edge(DOWN, buff=0.5)
            self.add(tag)
        self.wait(2.2)
        vo.finish(tail=0.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)
