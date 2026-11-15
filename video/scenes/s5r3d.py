"""S5R in 3D: the recorded rover mission replayed on a stylised low-poly Mars terrain.

Same data as the 2D replay (video/rover.json + cache/rover/mission.json from tools/fetch_rover.py): the map, the
scrambled controls and every recorded move are real; only the look (terrain, 3D rover) is an illustration.
Unseen cells stay dark until the rover's sensor (Manhattan radius 2) reaches them; the four buttons show "?" until
the rover has tried them. Narration key "S5R" (line 0). The chart follows in s5r_rover.py S5RChart.
"""
from __future__ import annotations

import json
import random

import numpy as np
from manim import (
    DEGREES, DOWN, LEFT, OUT, PI, RIGHT, UP, Cylinder, FadeIn, FadeOut, Group, LaggedStart, Prism, Rectangle,
    Sphere, Text, ThreeDScene, VGroup, rate_functions,
)

from common import (
    Narration,
    ACCENT, GOOD, LINE_STRONG, MONO, SANS, TEXT_1, TEXT_2, TEXT_3, VIDEO, load_json,
)

random.seed(4)
ROCK = ["#6e3b25", "#7d4329", "#5f331f"]
SAND = ["#b5582f", "#a64f2a", "#c0663a", "#9d4a27"]
FOG3D = "#1d1d21"
HEADING = {"north": 0.0, "west": PI / 2, "south": PI, "east": -PI / 2}
STEP = {"north": (-1, 0), "south": (1, 0), "west": (0, -1), "east": (0, 1)}


def rover_3d(u: float) -> Group:
    """Low-poly 3D rover facing +y (north), bottom at z = 0 (original design)."""
    g = Group()
    for sx in (-1, 1):
        for sy in (-0.32, 0, 0.32):
            w = Cylinder(radius=u * 0.11, height=u * 0.1, direction=RIGHT, resolution=(10, 2), checkerboard_colors=False,
                         fill_color="#26262a", fill_opacity=1, stroke_width=0)
            g.add(w.move_to([sx * u * 0.36, sy * u, u * 0.11]))
    body = Prism(dimensions=[u * 0.56, u * 0.8, u * 0.16], fill_color="#e4dfd4", fill_opacity=1, stroke_width=0)
    body.move_to([0, 0, u * 0.26])
    panel = Prism(dimensions=[u * 0.5, u * 0.36, u * 0.03], fill_color="#2f5fb3", fill_opacity=1, stroke_width=0)
    panel.move_to([0, -u * 0.14, u * 0.36])
    mast = Prism(dimensions=[u * 0.05, u * 0.05, u * 0.3], fill_color="#d8d8d8", fill_opacity=1, stroke_width=0)
    mast.move_to([0, u * 0.26, u * 0.49])
    head = Sphere(radius=u * 0.08, resolution=(8, 6), checkerboard_colors=False, fill_color="#e8e8e8",
                  fill_opacity=1, stroke_width=0)
    head.move_to([0, u * 0.28, u * 0.66])
    g.add(body, panel, mast, head)
    g.body = body
    return g


class S5RRover3D(ThreeDScene):
    def construct(self):
        cfg = json.loads((VIDEO / "rover.json").read_text(encoding="utf-8"))
        ms = load_json("rover/mission.json")
        vo = Narration(self, "S5R")
        n = ms["size"]
        cell = 5.4 / n
        walls = {tuple(w) for w in ms["walls"]}
        base, goal = tuple(ms["base"]), tuple(ms["goal"])
        path = [tuple(p) for p in ms["path"]]
        acts, events = ms["actions"], ms["events"]
        world = np.array([-3.2, -0.6, 0])          # terrain sits left of centre; the panel goes on the right

        def at(r, c, z=0.0):
            return world + np.array([(c - (n - 1) / 2) * cell, ((n - 1) / 2 - r) * cell, z])

        self.set_camera_orientation(phi=58 * DEGREES, theta=-90 * DEGREES, zoom=1.0)

        # ---- terrain: every cell starts as dark fog, becomes sand or rock when the sensor sees it ----
        heights, fog, real = {}, {}, {}
        for r in range(n):
            for c in range(n):
                rock = (r, c) in walls
                h = random.uniform(0.55, 0.95) * cell if rock else random.uniform(0.03, 0.12) * cell
                if (r, c) == base:
                    h = 0.04 * cell
                heights[(r, c)] = h
                f = Prism(dimensions=[cell * 0.96, cell * 0.96, 0.02 * cell], fill_color=FOG3D, fill_opacity=1,
                          stroke_width=0).move_to(at(r, c, 0.01 * cell))
                fog[(r, c)] = f
                side = cell * (0.88 if rock else 1.0)
                real[(r, c)] = Prism(dimensions=[side, side, h], fill_color=random.choice(ROCK if rock else SAND),
                                     fill_opacity=1, stroke_width=0).move_to(at(r, c, h / 2))
        pad = Prism(dimensions=[cell * 0.8, cell * 0.8, 0.03 * cell], fill_color="#d9d9d9", fill_opacity=1,
                    stroke_width=0).move_to(at(*base, heights[base] + 0.015 * cell))
        beacon = Group(
            Prism(dimensions=[cell * 0.1, cell * 0.1, cell * 0.85], fill_color=ACCENT, fill_opacity=1, stroke_width=0)
            .move_to(at(*goal, heights[goal] + cell * 0.425)),
            Sphere(radius=cell * 0.1, resolution=(8, 6), checkerboard_colors=False, fill_color=ACCENT, fill_opacity=1,
                   stroke_width=0).move_to(at(*goal, heights[goal] + cell * 0.9)),
        )
        known = set()

        def reveal(pos):
            for (r, c) in list(fog):
                if (r, c) not in known and abs(r - pos[0]) + abs(c - pos[1]) <= 2:
                    known.add((r, c))
                    self.remove(fog[(r, c)])
                    self.add(real[(r, c)])
                    if (r, c) == base:
                        self.add(pad)
                    if (r, c) == goal:
                        self.add(beacon)

        rover = rover_3d(cell * 1.6)
        rover_h = rover.get_depth()

        def rover_at(pos):
            return at(*pos, heights[pos] + rover_h / 2)

        rover.move_to(rover_at(base))

        # ---- panel (fixed to the screen) ----
        head = Text("separate test: a rover mission", font=SANS, font_size=26, color=TEXT_1).move_to([0, 3.0, 0])
        head.align_to([1.4, 0, 0], LEFT)
        who = Text(cfg["mission"]["who"], font=MONO, font_size=14, color=TEXT_3).next_to(head, DOWN, buff=0.12).align_to(head, LEFT)
        task = Text("scrambled controls · find the beacon\ndrive home before the battery runs out",
                    font=MONO, font_size=16, color=TEXT_2, line_spacing=0.9).next_to(who, DOWN, buff=0.3).align_to(head, LEFT)
        keys, key_idx = VGroup(), {}
        for a in ("ACTION1", "ACTION2", "ACTION3", "ACTION4"):
            box = Rectangle(width=3.4, height=0.46, stroke_color=LINE_STRONG, stroke_width=2, fill_opacity=0)
            keys.add(VGroup(box, Text(f"{a}  ?", font=MONO, font_size=18, color=TEXT_2).move_to(box)))
            key_idx[a] = len(keys) - 1
        keys.arrange(DOWN, buff=0.1).next_to(task, DOWN, buff=0.4).align_to(head, LEFT)
        steps_t = Text("step 0", font=MONO, font_size=14, color=TEXT_3).next_to(keys, DOWN, buff=0.3).align_to(head, LEFT)
        self.add_fixed_in_frame_mobjects(head, who, task, keys, steps_t)
        self.remove(head, who, task, keys, steps_t)

        vo.cue(0, delay=0.3)
        reveal(base)
        hidden_fog = [fog[p] for p in fog if p not in known]
        self.play(LaggedStart(*[FadeIn(m) for m in hidden_fog], lag_ratio=0.005), FadeIn(rover),
                  FadeIn(head), FadeIn(who), run_time=0.8)
        self.play(FadeIn(task), LaggedStart(*[FadeIn(k) for k in keys], lag_ratio=0.1), run_time=0.6)

        # ---- replay every recorded move, paced to the spoken line ----
        step_time = min(0.55, max(0.2, (vo.dur(0) - 1.8) / max(1, len(acts))))
        heading, learned = 0.0, set()
        for i, a in enumerate(acts):
            k = keys[key_idx[a]]
            k[0].set_stroke(ACCENT, width=3)
            d = ms["mapping"][a]
            pos, prev = path[i + 1], path[i]
            turn = (HEADING[d] - heading + PI) % (2 * PI) - PI
            heading = HEADING[d]
            if abs(turn) > 1e-3:
                self.play(rover.animate.rotate(turn, axis=OUT), run_time=step_time * 0.3)
            if pos != prev:
                self.play(rover.animate.move_to(rover_at(pos)), run_time=step_time * 0.55, rate_func=rate_functions.smooth)
            else:  # bump: lurch towards the wall and back
                dr, dc = STEP[d]
                self.play(rover.animate.shift(np.array([dc, -dr, 0]) * cell * 0.18), run_time=step_time * 0.45,
                          rate_func=rate_functions.there_and_back)
            reveal(pos)
            if a not in learned and "moved" in events[i]:
                learned.add(a)
                new = Text(f"{a}  drives {d}", font=MONO, font_size=18, color=ACCENT).move_to(k[1])
                old = k[1]
                k.remove(old)
                self.remove(old)
                k.add(new)
                self.add_fixed_in_frame_mobjects(new)
            label = f"step {i + 1}" + ("  · beacon found" if "BEACON" in events[i] else "") \
                + ("  · MISSION SUCCESS" if "SUCCESS" in events[i] else "")
            new_steps = Text(label, font=MONO, font_size=14, color=GOOD if "SUCCESS" in events[i] else TEXT_3)
            new_steps.next_to(keys, DOWN, buff=0.3).align_to(head, LEFT)
            self.remove(steps_t)
            steps_t = new_steps
            self.add_fixed_in_frame_mobjects(steps_t)
            self.wait(step_time * 0.15)
            k[0].set_stroke(LINE_STRONG, width=2)
        if ms["success"]:
            self.play(rover.body.animate.set_fill(GOOD), run_time=0.3)
        # a slow orbit to show the terrain while the line finishes
        self.move_camera(theta=-70 * DEGREES, run_time=1.2)
        vo.finish(tail=0.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)
