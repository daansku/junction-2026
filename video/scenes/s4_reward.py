"""S4 Reward integrity. See SCRIPT.md S4.

Numbers: coordination/JUDGING.md Harbor results (dev game, Harbor 0.26.0 + Docker):
oracle 1.000 (92 actions, 6/6), nop 0.000, stop after level 1 0.167 (13 actions, 1/6).
"""
from __future__ import annotations

from manim import (
    Group,
    DOWN, LEFT, RIGHT, UP, Create, FadeIn, FadeOut, Rectangle, RoundedRectangle, Scene, Text,
    VGroup, Line, Arrow,
)

from common import (
    ACCENT, BAD, GOOD, LINE_STRONG, MONO, SANS, TEXT_1, TEXT_2, TEXT_3, agent_sprite, PALETTE,
)

HARBOR = [
    # (label, actions, levels, score)
    ("do nothing", "0 actions", "0/6 levels", 0.000),
    ("stop after level 1", "13 actions", "1/6 levels", 0.167),
    ("reference run", "92 actions", "6/6 levels", 1.000),
]


class S4Reward(Scene):
    def construct(self):
        # ---- the scoring rule as a picture ----
        title = Text("score per level", font=MONO, font_size=20, color=TEXT_2).to_edge(UP, buff=0.6)
        solved = VGroup(
            Text("solved:", font=SANS, font_size=30, color=TEXT_1),
            Text("optimal moves", font=MONO, font_size=28, color=ACCENT),
        ).arrange(RIGHT, buff=0.3)
        frac_line = Line(LEFT * 1.6, RIGHT * 1.6, stroke_color=TEXT_1, stroke_width=2)
        denom = Text("moves used", font=MONO, font_size=28, color=TEXT_1)
        frac = VGroup(solved[1], frac_line, denom).arrange(DOWN, buff=0.12)
        row1 = VGroup(solved[0], frac).arrange(RIGHT, buff=0.35)
        row2 = VGroup(Text("not solved:", font=SANS, font_size=30, color=TEXT_1),
                      Text("0", font=MONO, font_size=34, color=BAD)).arrange(RIGHT, buff=0.35)
        rule = VGroup(row1, row2).arrange(DOWN, aligned_edge=LEFT, buff=0.5).move_to(UP * 0.6)
        avg = Text("game score = mean over all levels", font=MONO, font_size=18, color=TEXT_3).next_to(rule, DOWN, buff=0.5)
        self.play(FadeIn(title), FadeIn(row1, shift=UP * 0.1), run_time=0.7)
        self.play(FadeIn(row2, shift=UP * 0.1), FadeIn(avg), run_time=0.6)
        self.wait(1.6)
        self.play(FadeOut(VGroup(title, rule, avg)), run_time=0.4)

        # ---- shortcuts and their real Harbor scores ----
        cards = VGroup()
        for label, acts, levels, score in HARBOR:
            box = Rectangle(width=3.6, height=3.0, stroke_color=LINE_STRONG, stroke_width=2, fill_opacity=0)
            name = Text(label, font=SANS, font_size=22, color=TEXT_1)
            facts = Text(f"{acts} · {levels}", font=MONO, font_size=15, color=TEXT_3)
            num = Text(f"{score:.3f}", font=MONO, font_size=54, color=GOOD if score == 1 else (BAD if score == 0 else ACCENT))
            VGroup(name, num, facts).arrange(DOWN, buff=0.3).move_to(box)
            cards.add(VGroup(box, name, num, facts))
        cards.arrange(RIGHT, buff=0.35).move_to(UP * 0.4)
        src = Text("judges' harness: Harbor 0.26.0 + Docker, same game", font=MONO, font_size=14, color=TEXT_3).next_to(cards, DOWN, buff=0.3)
        for c in cards:
            self.play(FadeIn(c, shift=UP * 0.15), run_time=0.5)
            self.wait(0.4)
        self.play(FadeIn(src), run_time=0.3)
        reset = Text("RESET never erases moves: every action before it still counts", font=SANS, font_size=22, color=TEXT_2)
        reset.next_to(src, DOWN, buff=0.35)
        self.play(FadeIn(reset), run_time=0.4)
        self.wait(1.4)
        self.play(FadeOut(VGroup(cards, src, reset)), run_time=0.4)

        # ---- sealed grader ----
        agent_box = RoundedRectangle(corner_radius=0.05, width=4.2, height=3.0, stroke_color=LINE_STRONG, stroke_width=2).shift(LEFT * 3.3)
        game_box = RoundedRectangle(corner_radius=0.05, width=3.2, height=3.0, stroke_color=LINE_STRONG, stroke_width=2)
        grade_box = RoundedRectangle(corner_radius=0.05, width=3.2, height=3.0, stroke_color=ACCENT, stroke_width=3).shift(RIGHT * 3.8)
        a_lab = Text("agent container", font=MONO, font_size=16, color=TEXT_2).next_to(agent_box, UP, buff=0.1)
        g_lab = Text("game sidecar", font=MONO, font_size=16, color=TEXT_2).next_to(game_box, UP, buff=0.1)
        v_lab = Text("verifier container", font=MONO, font_size=16, color=ACCENT).next_to(grade_box, UP, buff=0.1)
        bot = agent_sprite(PALETTE[15], unit=0.16).move_to(agent_box)
        g_txt = Text("observe()\nact()", font=MONO, font_size=18, color=TEXT_1).move_to(game_box)
        v_txt = Text("score.json\ngraded after\nthe agent stops", font=MONO, font_size=15, color=TEXT_1).move_to(grade_box)
        link = Arrow(agent_box.get_right(), game_box.get_left(), buff=0.05, stroke_color=TEXT_2, stroke_width=3)
        link2 = Arrow(game_box.get_right(), grade_box.get_left(), buff=0.05, stroke_color=ACCENT, stroke_width=3)
        mcp = Text("MCP", font=MONO, font_size=13, color=TEXT_3).next_to(link, UP, buff=0.05)
        self.play(Create(agent_box), Create(game_box), FadeIn(a_lab), FadeIn(g_lab), FadeIn(bot), FadeIn(g_txt), run_time=0.8)
        self.play(FadeIn(link), FadeIn(mcp), run_time=0.4)
        self.play(Create(grade_box), FadeIn(v_lab), FadeIn(v_txt), FadeIn(link2), run_time=0.8)
        no = Text("agent cannot reach the score", font=SANS, font_size=22, color=TEXT_2).to_edge(DOWN, buff=0.8)
        self.play(FadeIn(no), run_time=0.4)
        self.wait(1.6)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)
