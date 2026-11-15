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
    Narration, ACCENT,
    FAILURE_MODES, LINE_STRONG, MONO, PALETTE, PLACEHOLDER, SANS, TEXT_1, TEXT_2, TEXT_3,
    agent_sprite,
)

random.seed(5)
# values: video/s5_training.json


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

        # ---- the result: base vs RL on our games (values from video/s5_training.json) ----
        import json
        from common import VIDEO, GOOD
        res = json.loads((VIDEO / "s5_training.json").read_text(encoding="utf-8"))
        num_color = TEXT_1 if res.get("final") else PLACEHOLDER
        title = Text(res["title"], font=SANS, font_size=24, color=TEXT_1).next_to(q, DOWN, buff=0.35)
        sub = Text(res["sub"], font=MONO, font_size=14, color=TEXT_3).next_to(title, DOWN, buff=0.12)
        lo, hi, width, x0 = 0.5, 0.75, 7.0, -2.0

        def x(v):
            return x0 + (v - lo) / (hi - lo) * width

        labels, bars, nums = VGroup(), [], VGroup()
        y = 0.4
        for row in res["rows"]:
            lab = Text(row["label"], font=SANS, font_size=20, color=TEXT_1 if row["kind"] == "ours" else TEXT_2)
            lab.move_to([x0 - 0.3 - lab.width / 2, y, 0])
            bar = Rectangle(width=x(row["score"]) - x0, height=0.5, fill_color="#199e70" if row["kind"] == "ours" else "#3987e5",
                            fill_opacity=1, stroke_width=0)
            bar.move_to([x0 + bar.width / 2, y, 0])
            nums.add(Text(f"{row['score']:.3f}", font=MONO, font_size=18, color=num_color).next_to(bar, RIGHT, buff=0.15))
            labels.add(lab)
            bars.append(bar)
            y -= 0.95
        axis = Line([x0, 0.85, 0], [x0, y + 0.45, 0], stroke_color=LINE_STRONG, stroke_width=1)
        axis_note = Text(f"axis starts at {lo:.2f}", font=MONO, font_size=12, color=TEXT_3).next_to(axis, DOWN, buff=0.08)
        delta = VGroup(*[Text(t, font=MONO, font_size=16, color=TEXT_2) for t in res["method"]])
        delta.arrange(DOWN, buff=0.12).move_to([0, y - 0.2, 0])
        foot = Text(res["footnote"], font=MONO, font_size=13, color=TEXT_3).next_to(delta, DOWN, buff=0.2)
        self.play(FadeIn(title), FadeIn(sub), FadeIn(labels), FadeIn(axis), FadeIn(axis_note), run_time=0.5)
        self.play(LaggedStart(*[GrowFromEdge(b, LEFT) for b in bars], lag_ratio=0.3, run_time=1.2))
        self.play(FadeIn(nums), run_time=0.4)
        self.play(FadeIn(delta, shift=UP * 0.1), FadeIn(foot), run_time=0.5)
        if not res.get("final"):
            tag = Text("PRELIMINARY: larger fresh test (1,400 items) pending", font=MONO, font_size=16, color=PLACEHOLDER)
            tag.to_edge(DOWN, buff=0.35)
            self.add(tag)
        self.wait(1.5)
        vo.finish(tail=0.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)
