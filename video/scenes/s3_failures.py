"""S3 Why failures are meaningful: several real replays, scroll between them, pan out.
See SCRIPT.md S3. Replays are runs from rules.json failure-mode examples (cache/steps/).
"""
from __future__ import annotations

import random

from manim import (
    DOWN, LEFT, ORIGIN, RIGHT, UP, FadeIn, FadeOut, Group, Rectangle, Scene, Text, VGroup,
    rate_functions,
)

from common import (
    Narration,
    CACHE, FAILURE_MODES, MODE_COLOR, MONO, SANS, TEXT_1, TEXT_2, TEXT_3, frame_image, framed,
    load_json, set_frame,
)

random.seed(11)
# (run_id, first step, last step, failure mode, player name)
REPLAYS = [
    ("20261114T015741-02f65e44", 15, 27, "no_effect_loop", "Nemotron 3.5 Super VL"),
    ("20261114T015741-3858885a", 108, 123, "late_reset", "Kimi K3.1 Pro"),
    ("20261114T015741-8260dc79", 98, 109, "belief_mismatch", "Kimi K3.1 Pro"),
]
SPACING = 12.0
FRAME_H = 4.6


def mode_label(mode: str) -> str:
    return next(t for m, t, _ in FAILURE_MODES if m == mode)


def wrap(text: str, width_chars: int = 46, lines: int = 3) -> str:
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width_chars:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] += " …"
    return "\n".join(out)


class S3Failures(Scene):
    def panel(self, idx: int):
        rid, a, b, mode, who = REPLAYS[idx]
        steps = load_json(f"steps/{rid}.json")
        img = frame_image(steps[a]["frame"], height=FRAME_H)
        border = framed(img)
        color = MODE_COLOR[mode]
        tag = Text(mode_label(mode), font=SANS, font_size=22, color=color).next_to(img, DOWN, buff=0.2)
        who_t = Text(who, font=MONO, font_size=16, color=TEXT_3).next_to(img, UP, buff=0.12).align_to(img, LEFT)
        hyp = Text("", font=MONO, font_size=15, color=TEXT_2)
        p = Group(img, border, tag, who_t)
        p.shift(RIGHT * idx * SPACING + LEFT * 2.0)
        return p, img, steps, a, b, color

    def play_steps(self, img, steps, a, b, color, step_time):
        hyp_box = None
        last_hyp = None
        for k in range(a + 1, b + 1):
            st = steps[k]
            set_frame(img, st["frame"])
            h = st.get("hypothesis") or ""
            if h and h != last_hyp:
                if hyp_box is not None:
                    self.remove(hyp_box)
                hyp_box = Text("model thinks:\n" + wrap(h), font=MONO, font_size=15, color=TEXT_2, line_spacing=0.9)
                hyp_box.next_to(img, RIGHT, buff=0.45).align_to(img, UP)
                self.add(hyp_box)
                last_hyp = h
            ev = (st.get("truth") or {}).get("events") or []
            if "bump" in ev or "reset" in ev:
                fl = framed(img).set_stroke(color, width=6)
                evt = Text("screen unchanged" if "bump" in ev else "RESET", font=MONO, font_size=16, color=color)
                evt.next_to(img, RIGHT, buff=0.45).align_to(img, DOWN)
                self.add(fl, evt)
                self.wait(step_time)
                self.remove(fl, evt)
            else:
                self.wait(step_time)
        return hyp_box

    def construct(self):
        panels = [self.panel(i) for i in range(len(REPLAYS))]
        vo = Narration(self, "S3")
        vo.cue(0, delay=0.2)
        world = Group(*[p[0] for p in panels])
        self.play(FadeIn(panels[0][0]), run_time=0.5)
        self.add(world)
        hyp = None
        for i, (p, img, steps, a, b, color) in enumerate(panels):
            if i > 0:
                vo.cue(i, delay=0.5)
                if hyp is not None:
                    self.play(FadeOut(hyp), run_time=0.2)
                self.play(world.animate.shift(LEFT * SPACING), run_time=0.9, rate_func=rate_functions.ease_in_out_cubic)
            # spread each replay over its spoken line (the first line also introduces the scene)
            span = vo.dur(i) - (2.5 if i == 0 else 0.6)
            hyp = self.play_steps(img, steps, a, b, color, min(0.35, max(0.12, span / (b - a))))
            self.wait(0.4)
        if hyp is not None:
            self.play(FadeOut(hyp), run_time=0.2)

        # ---- pull back: the three replays side by side, each with its failure label ----
        vo.cue(3, delay=0.3)
        self.play(world.animate.scale(0.45).move_to(ORIGIN), run_time=1.4, rate_func=rate_functions.ease_in_out_cubic)
        self.wait(1.0)
        vo.finish(tail=0.5)
        self.play(FadeOut(world), run_time=0.5)
