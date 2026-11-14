"""S1 The environment in 30 seconds. See video/SCRIPT.md S1.

Frames come from the engine (video/tools/export_engine.py -> cache/engine.json).
"""
from __future__ import annotations

from manim import (
    DOWN, LEFT, RIGHT, UP, Create, FadeIn, FadeOut, Group, LaggedStart, Rectangle, Scene,
    Text, VGroup, VMobject, rate_functions,
)

from common import (
    ACCENT, LINE_STRONG, MONO, SANS, TEXT_1, TEXT_2, TEXT_3, frame_image, framed, load_json,
    set_frame,
)

FRAME_H = 6.0


def band(img, row0: int, row1: int, color=ACCENT) -> Rectangle:
    """Outline rows row0..row1 (inclusive) of a 64-row frame image."""
    cell = img.height / 64
    h = (row1 - row0 + 1) * cell
    r = Rectangle(width=img.width + 0.12, height=h + 0.08, stroke_color=color, stroke_width=4, fill_opacity=0)
    r.move_to(img.get_top() + DOWN * (row0 * cell + h / 2))
    return r


class S1Environment(Scene):
    def construct(self):
        eng = load_json("engine.json")
        lv1 = eng["levels"][0]
        img = frame_image(lv1["frames"][0], height=FRAME_H).shift(LEFT * 2.6)
        border = framed(img)
        self.play(FadeIn(Group(img, border)), run_time=0.6)

        # ---- what the agent sees: three bands ----
        notes = [
            (0, 1, "move budget"),
            (3, 4, "level · inventory"),
            (6, 63, "playfield"),
        ]
        side = VGroup()
        prev_box = None
        for r0, r1, text in notes:
            box = band(img, r0, r1)
            lab = Text(text, font=MONO, font_size=22, color=ACCENT)
            lab.next_to(img, RIGHT, buff=0.5).align_to(box, UP)
            if r0 == 6:
                lab.move_to([lab.get_x(), box.get_center()[1], 0])
            anims = [Create(box), FadeIn(lab, shift=LEFT * 0.1)]
            if prev_box is not None:
                anims.append(FadeOut(prev_box))
            self.play(*anims, run_time=0.6)
            prev_box = box
            side.add(lab)
        facts = VGroup(
            Text("64 × 64 pixels · 16 colours", font=SANS, font_size=26, color=TEXT_1),
            Text("no text · no score · no rule names", font=SANS, font_size=26, color=TEXT_2),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.2).next_to(img, RIGHT, buff=0.5).shift(DOWN * 1.5)
        self.play(FadeOut(prev_box), FadeIn(facts, shift=UP * 0.1), run_time=0.6)
        self.wait(1.0)

        # ---- six buttons; replay the optimal path ----
        keys = VGroup()
        for name in ["RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5"]:
            t = Text(name, font=MONO, font_size=18, color=TEXT_1)
            box = Rectangle(width=t.width + 0.3, height=0.48, stroke_color=LINE_STRONG, stroke_width=2, fill_opacity=0)
            keys.add(VGroup(box, t.move_to(box)))
        keys.arrange(RIGHT, buff=0.12).next_to(img, RIGHT, buff=0.5).shift(DOWN * 0.1)
        self.play(FadeOut(side), FadeOut(facts), LaggedStart(*[FadeIn(k, shift=UP * 0.1) for k in keys], lag_ratio=0.08), run_time=0.8)
        key_of = {f"ACTION{i}": keys[i] for i in range(1, 6)}
        key_of["RESET"] = keys[0]
        for fr, a in zip(lv1["frames"][1:], lv1["optimal_path"]):
            k = key_of[a][0]
            k.set_stroke(ACCENT, width=3)
            set_frame(img, fr)
            self.wait(0.16)
            k.set_stroke(LINE_STRONG, width=2)
        self.wait(0.3)

        # ---- colours reshuffled per game ----
        skins = eng["skins"]
        skin_note = Text("same level, three games: colours reshuffled", font=MONO, font_size=20, color=TEXT_2)
        skin_note.next_to(img, RIGHT, buff=0.5)
        self.play(FadeOut(keys), FadeIn(skin_note), run_time=0.4)
        for s in skins + skins[:1]:
            set_frame(img, s)
            self.wait(0.7)

        # ---- one new hidden rule per level ----
        strip = Group()
        for lv in eng["levels"][:5]:
            t = frame_image(lv["frames"][0], height=1.55)
            cap = Text(f"L{lv['level']}  " + (lv["new_rule"] or "move + goal").replace("_", " "), font=MONO, font_size=14, color=TEXT_2)
            cap.next_to(t, DOWN, buff=0.1)
            strip.add(Group(t, framed(t), cap))
        strip.arrange(RIGHT, buff=0.25).move_to([0, 0.2, 0])
        self.play(FadeOut(skin_note), FadeOut(Group(img, border)), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(s, shift=UP * 0.2) for s in strip], lag_ratio=0.15), run_time=1.2)
        rule_note = Text("each level hides one new rule; the agent has to find it by experimenting",
                         font=SANS, font_size=22, color=TEXT_2).next_to(strip, DOWN, buff=0.5)
        self.play(FadeIn(rule_note), run_time=0.4)
        self.wait(1.4)

        # ---- proven solvable: draw the optimal path ----
        lv2 = eng["levels"][1]
        big = frame_image(lv2["frames"][0], height=FRAME_H)
        bborder = framed(big)
        self.play(FadeOut(rule_note), FadeOut(Group(*[s for i, s in enumerate(strip) if i != 1])),
                  strip[1].animate.scale_to_fit_height(FRAME_H * 1.1).move_to(big), run_time=0.8)
        self.remove(strip[1])
        self.add(big, bborder)
        cell = big.height / 64
        x0, y0 = big.get_corner(UP + LEFT)[0], big.get_corner(UP + LEFT)[1]

        def pix(p):
            x, y, cs = p
            return [x0 + (x + cs / 2) * cell, y0 - (y + cs / 2) * cell, 0]

        pts = [pix(lv2["start_pixel"])] + [pix(p) for p in lv2["optimal_pixels"]]
        path = VMobject(stroke_color=ACCENT, stroke_width=7).set_points_as_corners(pts)
        self.play(Create(path), run_time=1.6, rate_func=rate_functions.linear)
        proof = Text(f"proven solvable by search · optimal = {lv2['optimal_moves']} moves", font=MONO, font_size=20, color=ACCENT)
        proof.next_to(big, DOWN, buff=0.2)
        self.play(FadeIn(proof), run_time=0.4)
        self.wait(1.2)
        self.play(FadeOut(Group(big, bborder, path, proof)), run_time=0.5)
