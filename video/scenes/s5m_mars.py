"""S5M: the rover map turns into a stylised 3D terrain and the rover drives its last moves across it.

An illustration between the rover replay (S5RRover) and its results chart (S5RChart); no narration, no numbers.
Starts on exactly the frame the replay ends on (same map, same rover, same place), then tilts the camera.
Drop it by removing the "S5M" entry from narration.json.
"""
from __future__ import annotations

import random

import numpy as np
from manim import (
    DEGREES, ORIGIN, OUT, PI, RIGHT, UP, Cylinder, FadeIn, FadeOut, Group, LaggedStart, Prism, Sphere,
    Square, Text, ThreeDScene, VGroup, rate_functions,
)

from common import GOOD, MONO, PALETTE, TEXT_3, load_json
from s5r_rover import FLOOR, FOG, HEADING, WALL, rover_sprite

random.seed(4)
ROCK = ["#6e3b25", "#7d4329", "#5f331f"]
SAND = ["#b5582f", "#a64f2a", "#c0663a", "#9d4a27"]
DIRS = {"north": (-1, 0), "south": (1, 0), "west": (0, -1), "east": (0, 1)}


def rover_3d(u: float) -> Group:
    """Low-poly 3D rover built along +y (front), sitting on z = 0 (original design)."""
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
    head = Sphere(radius=u * 0.08, resolution=(8, 6), checkerboard_colors=False, fill_color="#e8e8e8", fill_opacity=1, stroke_width=0)
    head.move_to([0, u * 0.28, u * 0.66])
    g.add(body, panel, mast, head)
    g.body = body
    return g


class S5MMars(ThreeDScene):
    def construct(self):
        ms = load_json("rover/mission.json")
        n, cell = ms["size"], 5.6 / ms["size"]
        origin = np.array([-6.0, 2.5, 0])
        walls = {tuple(w) for w in ms["walls"]}
        base, goal = tuple(ms["base"]), tuple(ms["goal"])
        path = [tuple(p) for p in ms["path"]]
        acts = ms["actions"]

        def at(r, c, z=0.0):
            return origin + np.array([c * cell, -r * cell, z])

        # ---- the exact last frame of the replay ----
        known = set()
        for p in path:
            known |= {(r, c) for r in range(n) for c in range(n) if abs(r - p[0]) + abs(c - p[1]) <= 2}
        flat = VGroup()
        for r in range(n):
            for c in range(n):
                col = FOG if (r, c) not in known else (WALL if (r, c) in walls else FLOOR)
                flat.add(Square(side_length=cell * 0.94, stroke_width=0, fill_color=col, fill_opacity=1).move_to(at(r, c)))
        flat.add(Square(side_length=cell * 0.5, stroke_width=0, fill_color="#ffdc00", fill_opacity=1).move_to(at(*goal)))
        flat.add(Square(side_length=cell * 0.8, stroke_color="#f2f2f2", stroke_width=3, fill_opacity=0).move_to(at(*base)))
        last_dir = ms["mapping"][acts[-1]]
        top = rover_sprite(cell).rotate(HEADING[last_dir]).move_to(at(*path[-1]))
        top.body.set_fill(GOOD)
        self.add(flat, top)
        self.wait(0.1)

        # ---- terrain: floor becomes uneven sand, walls become rocks ----
        centre = at((n - 1) / 2, (n - 1) / 2)
        heights = {}
        terrain = Group()
        for r in range(n):
            for c in range(n):
                rock = (r, c) in walls
                h = random.uniform(0.55, 0.95) * cell if rock else random.uniform(0.03, 0.12) * cell
                heights[(r, c)] = h
                col = random.choice(ROCK if rock else SAND)
                pr = Prism(dimensions=[cell * (0.9 if rock else 1.0), cell * (0.9 if rock else 1.0), h],
                           fill_color=col, fill_opacity=1, stroke_width=0)
                pr.move_to(at(r, c, h / 2) - centre)
                terrain.add(pr)
        beacon = Prism(dimensions=[cell * 0.12, cell * 0.12, cell * 0.9], fill_color="#ffdc00", fill_opacity=1,
                       stroke_width=0).move_to(at(*goal, heights[goal] + cell * 0.45) - centre)
        tip = Sphere(radius=cell * 0.1, resolution=(8, 6), checkerboard_colors=False, fill_color="#ffdc00", fill_opacity=1,
                     stroke_width=0).move_to(at(*goal, heights[goal] + cell * 0.95) - centre)

        rover = rover_3d(cell * 1.7)
        rover.height_3d = rover.get_depth()

        def place(pos, direction):
            rover.move_to(at(*pos) - centre + np.array([0, 0, heights[pos] + rover.height_3d / 2]))

        # start the 3D rover where the drive begins: the last few moves of the real path
        k0 = max(0, len(acts) - 4)
        start = path[k0]
        first_dir = ms["mapping"][acts[k0]]
        rover.rotate(HEADING[first_dir], axis=OUT)
        place(start, first_dir)
        heading = HEADING[first_dir]

        self.play(Group(flat, top).animate.shift(-centre), run_time=0.6)
        self.move_camera(phi=64 * DEGREES, theta=-75 * DEGREES, zoom=1.55,
                         added_anims=[FadeOut(flat), FadeOut(top), LaggedStart(*[FadeIn(t, shift=OUT * 0.3) for t in terrain],
                                                                               lag_ratio=0.01),
                                      FadeIn(beacon), FadeIn(tip)],
                         run_time=1.5)
        note = Text("illustration", font=MONO, font_size=14, color=TEXT_3).to_corner(RIGHT + UP * -1, buff=0.3)
        self.add_fixed_in_frame_mobjects(note)
        self.play(FadeIn(rover), run_time=0.3)
        self.begin_ambient_camera_rotation(rate=0.12)

        # ---- drive the real last moves ----
        for a, p0, p1 in zip(acts[k0:], path[k0:-1], path[k0 + 1:]):
            d = ms["mapping"][a]
            turn = (HEADING[d] - heading + PI) % (2 * PI) - PI
            heading = HEADING[d]
            if abs(turn) > 1e-3:
                self.play(rover.animate.rotate(turn, axis=OUT), run_time=0.25)
            if p1 != p0:
                tgt = at(*p1) - centre + np.array([0, 0, heights[p1] + rover.height_3d / 2])
                self.play(rover.animate.move_to(tgt), run_time=0.45, rate_func=rate_functions.smooth)
        self.play(rover.body.animate.set_fill(GOOD), run_time=0.3)
        self.wait(0.2)
        self.stop_ambient_camera_rotation()
        self.play(FadeOut(Group(terrain, rover, beacon, tip)), FadeOut(note), run_time=0.5)
