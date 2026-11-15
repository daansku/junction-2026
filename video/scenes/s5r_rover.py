"""S5R Rover: transfer test outside our games (A3's edge rover experiment).

Everything shown comes from video/rover.json (bars, labels, which mission) and video/cache/rover/mission.json
(written by tools/fetch_rover.py). Change the rover segment by editing those two plus the "S5R" lines in
narration.json; this scene renders on its own, so nothing else needs re-rendering.
"""
from __future__ import annotations

import json

from manim import (
    DOWN, LEFT, RIGHT, UP, FadeIn, FadeOut, Group, GrowFromEdge, LaggedStart, Line, Rectangle, Scene,
    Square, Text, VGroup,
)

from common import (
    Narration,
    ACCENT, GOOD, LINE_STRONG, MONO, PALETTE, PLACEHOLDER, SANS, TEXT_1, TEXT_2, TEXT_3, VIDEO,
    agent_sprite, load_json,
)

FOG = "#1b1b1e"
FLOOR = "#000000"
WALL = PALETTE[5]
ARROW = {d: f"drives {d}" for d in ("north", "south", "west", "east")}
KIND_COLOR = {"frontier": "#3987e5", "small": TEXT_3, "ours": "#199e70"}


class S5RRover(Scene):
    def construct(self):
        cfg = json.loads((VIDEO / "rover.json").read_text(encoding="utf-8"))
        ms = load_json("rover/mission.json")
        vo = Narration(self, "S5R")
        n, cell = ms["size"], 0.62
        origin = [-6.3, 2.5, 0]

        def at(r, c):
            return [origin[0] + c * cell, origin[1] - r * cell, 0]

        walls = {tuple(w) for w in ms["walls"]}
        base, goal = tuple(ms["base"]), tuple(ms["goal"])
        cells = {}
        for r in range(n):
            for c in range(n):
                sq = Square(side_length=cell * 0.94, stroke_width=0, fill_color=FOG, fill_opacity=1).move_to(at(r, c))
                cells[(r, c)] = sq
        grid = VGroup(*cells.values())
        base_mark = Square(side_length=cell * 0.8, stroke_color=TEXT_1, stroke_width=3, fill_opacity=0).move_to(at(*base))
        base_lab = Text("B", font=MONO, font_size=16, color=TEXT_1).move_to(at(*base))
        beacon = Square(side_length=cell * 0.5, stroke_width=0, fill_color=ACCENT, fill_opacity=1).move_to(at(*goal))
        rover = agent_sprite(PALETTE[15], unit=cell * 0.14).move_to(at(*base))
        known = set()

        def reveal(pos):
            for (r, c), sq in cells.items():
                if (r, c) not in known and abs(r - pos[0]) + abs(c - pos[1]) <= 2:
                    known.add((r, c))
                    sq.set_fill(WALL if (r, c) in walls else FLOOR)
                    if (r, c) == goal:
                        self.add(beacon)

        head = Text("separate test: a rover mission", font=SANS, font_size=26, color=TEXT_1)
        head.move_to([0.0, 3.0, 0]).align_to([0.0, 0, 0], LEFT)
        who = Text(cfg["mission"]["who"], font=MONO, font_size=14, color=TEXT_3).next_to(head, DOWN, buff=0.12)
        task = Text("scrambled controls · find the beacon · drive home\nbefore the battery runs out",
                    font=MONO, font_size=16, color=TEXT_2, line_spacing=0.9).next_to(who, DOWN, buff=0.3).align_to(head, LEFT)
        who.align_to(head, LEFT)
        # the four buttons: their directions are unknown until the rover tries them
        keys, key_labels = VGroup(), {}
        for a in ("ACTION1", "ACTION2", "ACTION3", "ACTION4"):
            t = Text(f"{a}  ?", font=MONO, font_size=18, color=TEXT_2)
            box = Rectangle(width=3.4, height=0.46, stroke_color=LINE_STRONG, stroke_width=2, fill_opacity=0)
            keys.add(VGroup(box, t.move_to(box)))
            key_labels[a] = len(keys) - 1
        keys.arrange(DOWN, buff=0.1).next_to(task, DOWN, buff=0.4).align_to(head, LEFT)
        steps_t = Text("", font=MONO, font_size=14, color=TEXT_3)

        vo.cue(0, delay=0.3)
        reveal(base)
        self.play(FadeIn(grid), FadeIn(base_mark), FadeIn(base_lab), FadeIn(rover), FadeIn(head), FadeIn(who), run_time=0.7)
        self.play(FadeIn(task), LaggedStart(*[FadeIn(k) for k in keys], lag_ratio=0.1), run_time=0.7)

        # replay the recorded mission, paced to the spoken line
        acts, path, events = ms["actions"], ms["path"], ms["events"]
        step_time = min(0.5, max(0.18, (vo.dur(0) - 1.8) / max(1, len(acts))))
        learned = set()
        for i, a in enumerate(acts):
            k = keys[key_labels[a]]
            k[0].set_stroke(ACCENT, width=3)
            pos = tuple(path[i + 1])
            rover.move_to(at(*pos))
            reveal(pos)
            if a not in learned and "moved" in events[i]:
                learned.add(a)
                new = Text(f"{a}  {ARROW[ms['mapping'][a]]}", font=MONO, font_size=18, color=ACCENT).move_to(k[1])
                k.remove(k[1])
                k.add(new)
                self.add(new)
            new_steps = Text(f"step {i + 1}" + ("  · beacon found" if "BEACON" in events[i] else "")
                             + ("  · MISSION SUCCESS" if "SUCCESS" in events[i] else ""),
                             font=MONO, font_size=14, color=GOOD if "SUCCESS" in events[i] else TEXT_3)
            new_steps.next_to(keys, DOWN, buff=0.3).align_to(head, LEFT)
            self.remove(steps_t)
            steps_t = new_steps
            self.add(steps_t)
            self.wait(step_time)
            k[0].set_stroke(LINE_STRONG, width=2)
        if ms["success"]:
            self.play(rover.animate.set_fill(GOOD), run_time=0.3)
        self.wait(0.4)

        # ---- the chart: frontier vs the small model ----
        vo.cue(1, delay=0.4)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)
        title = Text(cfg["chart_title"], font=SANS, font_size=26, color=TEXT_1).to_edge(UP, buff=0.7)
        sub = Text(cfg["chart_sub"], font=MONO, font_size=14, color=TEXT_3).next_to(title, DOWN, buff=0.12)
        x0, width, y = -1.2, 6.0, 1.3
        rows = []
        for b in cfg["bars"]:
            lab = Text(b["label"], font=SANS, font_size=18, color=TEXT_1 if b["kind"] == "ours" else TEXT_2)
            lab.move_to([x0 - 0.3 - lab.width / 2, y, 0])
            if b.get("k") is None:
                bar = Rectangle(width=width, height=0.4, stroke_color=PLACEHOLDER, stroke_width=2, fill_opacity=0)
                bar.move_to([x0 + width / 2, y, 0])
                num = Text(b.get("placeholder", "pending"), font=MONO, font_size=15, color=PLACEHOLDER).move_to(bar)
                ci = VGroup()
            else:
                p = b["k"] / b["n"]
                bar = Rectangle(width=max(0.03, width * p), height=0.4, fill_color=KIND_COLOR[b["kind"]],
                                fill_opacity=1, stroke_width=0)
                bar.move_to([x0 + bar.width / 2, y, 0])
                xa, xb = x0 + width * b["lo"], x0 + width * b["hi"]
                ci = VGroup(Line([xa, y, 0], [xb, y, 0], stroke_color=TEXT_1, stroke_width=2),
                            Line([xa, y - 0.1, 0], [xa, y + 0.1, 0], stroke_color=TEXT_1, stroke_width=2),
                            Line([xb, y - 0.1, 0], [xb, y + 0.1, 0], stroke_color=TEXT_1, stroke_width=2))
                num = Text(f"{b['k']}/{b['n']}", font=MONO, font_size=15, color=TEXT_1)
                num.move_to([max(xb, bar.get_right()[0]) + 0.15 + num.width / 2, y, 0])
            rows.append((b, lab, bar, ci, num))
            y -= 0.85
        axis = Line([x0, 1.75, 0], [x0, y + 0.4, 0], stroke_color=LINE_STRONG, stroke_width=1)
        self.play(FadeIn(title), FadeIn(sub), FadeIn(axis), run_time=0.5)
        ours = [r for r in rows if r[0]["kind"] == "ours"]
        first = [r for r in rows if r[0]["kind"] != "ours"]
        self.play(LaggedStart(*[FadeIn(r[1]) for r in first], lag_ratio=0.1), run_time=0.5)
        self.play(LaggedStart(*[GrowFromEdge(r[2], LEFT) for r in first], lag_ratio=0.15), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(VGroup(r[3], r[4])) for r in first], lag_ratio=0.1), run_time=0.6)
        if any(r[0].get("k") is None for r in rows):
            tag = Text("PLACEHOLDER: rover runs still in progress", font=MONO, font_size=16, color=PLACEHOLDER).to_edge(DOWN, buff=0.4)
            self.add(tag)

        # ---- our model's row ----
        vo.cue(2, delay=0.2)
        for b, lab, bar, ci, num in ours:
            self.play(FadeIn(lab), GrowFromEdge(bar, LEFT), run_time=0.8)
            self.play(FadeIn(VGroup(ci, num)), run_time=0.4)
        self.wait(1.0)
        vo.finish(tail=0.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)
