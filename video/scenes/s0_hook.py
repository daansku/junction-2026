"""S0 Hook: break one agent, break many; the pieces line up into the failure-mode chart,
then rebuild into a game frame. See video/SCRIPT.md S0.

Render draft:  video/.venv/Scripts/manim.exe -ql video/scenes/s0_hook.py S0Hook
"""
from __future__ import annotations

import math
import random

import numpy as np
from manim import (
    DOWN, LEFT, ORIGIN, RIGHT, UP, AnimationGroup, FadeIn, FadeOut, Group, LaggedStart,
    Rectangle, Scene, Square, Text, VGroup, Write, linear, rate_functions, smooth,
)

from common import (
    BG, FAILURE_MODES, LINE, LINE_STRONG, PALETTE, TEXT_1, TEXT_2, TEXT_3, agent_sprite,
    frame_array, frame_cells, frame_image, framed, label, load_json, MONO,
)

random.seed(7)


def shatter_pieces(sprite: VGroup, color: str) -> VGroup:
    """Copy the sprite's cells as shards in the failure colour."""
    pieces = VGroup()
    for sq in sprite:
        p = sq.copy()
        p.set_fill(color, 1)
        pieces.add(p)
    return pieces


class S0Hook(Scene):
    def construct(self):
        rules = load_json("derived/rules.json")
        counts = {m["mode"]: m["count"] for m in rules["failure_modes"]}
        replay = load_json("steps/20261114T015741-02f65e44.json")
        end_frame = replay[16]["frame"]

        # ---------------- 0:00 one agent breaks ----------------
        floor = Rectangle(width=9, height=0.06, fill_color=LINE_STRONG, fill_opacity=1, stroke_width=0).shift(DOWN * 0.8)
        wall = Rectangle(width=0.35, height=2.2, fill_color=PALETTE[5], fill_opacity=1, stroke_width=0)
        wall.next_to(floor, UP, buff=0).shift(RIGHT * 2.5)
        agent = agent_sprite(PALETTE[15], unit=0.22).next_to(floor, UP, buff=0).shift(LEFT * 3)
        self.play(FadeIn(floor), FadeIn(wall), FadeIn(agent, shift=UP * 0.2), run_time=0.8)
        # walk into the wall: three hops
        for _ in range(3):
            self.play(agent.animate.shift(RIGHT * 1.45), run_time=0.35, rate_func=smooth)
        self.play(agent.animate.shift(RIGHT * 0.1), run_time=0.12, rate_func=rate_functions.there_and_back)

        red = FAILURE_MODES[0][2]
        pieces = shatter_pieces(agent, red)
        self.remove(agent)
        self.add(pieces)
        left = VGroup(*[p for p in pieces if p.get_x() < agent.get_x()])
        right = VGroup(*[p for p in pieces if p.get_x() >= agent.get_x()])
        self.play(
            left.animate.shift(LEFT * 0.5 + DOWN * 0.15).rotate(0.35),
            right.animate.shift(RIGHT * 0.15 + UP * 0.1).rotate(-0.5),
            run_time=0.7, rate_func=rate_functions.ease_out_cubic,
        )
        self.wait(1.4)

        # ---------------- 0:06 zoom out: many agents breaking ----------------
        wall_runs = load_json("runs.json")
        tiles_src = []
        import pathlib
        from common import CACHE
        for p in sorted((CACHE / "wall").glob("*.json")):
            tiles_src.append(load_json(f"wall/{p.name}"))
        cols, rows = 16, 9
        tile_h = 0.72
        gap = 0.1
        tiles = Group()
        shards_all = VGroup()
        shard_mode = []
        weights = [math.log10(counts.get(m, 1) + 1) for m, _, _ in FAILURE_MODES]
        for r in range(rows):
            for c in range(cols):
                src = tiles_src[(r * cols + c) % len(tiles_src)]
                fr = src["frames"][random.randrange(len(src["frames"]))]["frame"]
                img = frame_image(fr, height=tile_h)
                img.move_to([(c - (cols - 1) / 2) * (tile_h + gap), ((rows - 1) / 2 - r) * (tile_h + gap), 0])
                tiles.add(img)
        grid_scale_start = 3.2
        tiles.scale(grid_scale_start).shift(RIGHT * 0)  # start zoomed in
        self.play(
            FadeOut(VGroup(floor, wall, left, right)),
            FadeIn(tiles),
            run_time=0.6,
        )
        # zoom out
        self.play(tiles.animate.scale(1 / grid_scale_start), run_time=2.2, rate_func=rate_functions.ease_in_out_cubic)

        # every tile breaks into one failure colour (lagged, fast)
        mode_idx = random.choices(range(len(FAILURE_MODES)), weights=weights, k=len(tiles))
        breaks = []
        for t, mi in zip(tiles, mode_idx):
            color = FAILURE_MODES[mi][2]
            n = 4
            s = t.height / n
            for i in range(n):
                for j in range(n):
                    sq = Square(side_length=s * 0.9, stroke_width=0, fill_color=color, fill_opacity=1)
                    sq.move_to(t.get_corner(UP + LEFT) + RIGHT * (j + 0.5) * s + DOWN * (i + 0.5) * s)
                    shards_all.add(sq)
                    shard_mode.append(mi)
            breaks.append(t)
        order = list(range(len(tiles)))
        random.shuffle(order)
        anims = []
        for k in order:
            t = tiles[k]
            grp = VGroup(*shards_all[k * 16:(k + 1) * 16])
            anims.append(AnimationGroup(FadeOut(t, scale=0.6), FadeIn(grp, scale=1.4), run_time=0.35))
        self.play(LaggedStart(*anims, lag_ratio=0.02, run_time=3.0))
        self.wait(0.3)

        # ---------------- 0:12 shards line up into the failure-mode chart ----------------
        chart_w = 11.0
        bar_w = 1.25
        base_y = -2.6
        max_h = 4.6
        log_max = math.log10(max(counts.values()))
        bars, labels, nums, targets = VGroup(), VGroup(), VGroup(), []
        for i, (mode, text, color) in enumerate(FAILURE_MODES):
            x = (i - (len(FAILURE_MODES) - 1) / 2) * (chart_w / len(FAILURE_MODES))
            h = max(0.25, max_h * math.log10(counts.get(mode, 1)) / log_max)
            bar = Rectangle(width=bar_w, height=h, fill_color=color, fill_opacity=1, stroke_width=0)
            bar.move_to([x, base_y + h / 2, 0])
            bars.add(bar)
            lab = Text(text, font="IBM Plex Sans", font_size=17, color=TEXT_2, line_spacing=0.8)
            if lab.width > 1.7:
                words = text.split(" ")
                mid = len(words) // 2
                lab = Text(" ".join(words[:mid]) + "\n" + " ".join(words[mid:]), font="IBM Plex Sans",
                           font_size=17, color=TEXT_2, line_spacing=0.8)
            lab.next_to(bar, DOWN, buff=0.18)
            labels.add(lab)
            num = Text(f"{counts.get(mode, 0):,}", font=MONO, font_size=20, color=TEXT_1).next_to(bar, UP, buff=0.12)
            nums.add(num)
        axis = Rectangle(width=chart_w + 0.4, height=0.03, fill_color=LINE_STRONG, fill_opacity=1, stroke_width=0).move_to([0, base_y, 0])

        # each shard flies into a cell inside its bar
        moves = []
        for mi in range(len(FAILURE_MODES)):
            idx = [k for k, m in enumerate(shard_mode) if m == mi]
            bar = bars[mi]
            n = len(idx)
            if n == 0:
                continue
            per_row = 5
            nrows = math.ceil(n / per_row)
            cw = bar.width / per_row
            ch = bar.height / nrows
            for j, k in enumerate(idx):
                rr, cc = divmod(j, per_row)
                target = bar.get_corner(DOWN + LEFT) + RIGHT * (cc + 0.5) * cw + UP * (rr + 0.5) * ch
                sq = shards_all[k]
                moves.append(sq.animate.move_to(target).stretch_to_fit_width(cw * 0.92).stretch_to_fit_height(max(ch * 0.92, 0.01)))
        self.play(LaggedStart(*moves, lag_ratio=0.0008, run_time=2.4, rate_func=rate_functions.ease_in_out_cubic))
        self.play(FadeIn(bars), FadeOut(shards_all), FadeIn(axis), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(l, shift=UP * 0.1) for l in labels], lag_ratio=0.1),
                  LaggedStart(*[FadeIn(n) for n in nums], lag_ratio=0.1), run_time=1.0)
        note = Text("failure-mode counts, all model runs (log scale)", font=MONO, font_size=14, color=TEXT_3)
        note.to_corner(UP + LEFT, buff=0.5)
        self.play(FadeIn(note), run_time=0.4)
        self.wait(1.6)

        # ---------------- 0:17 bars collapse into a game frame ----------------
        cells = frame_cells(end_frame, size=6.4)
        border = framed(cells.copy().set_opacity(0)).set(width=6.4, height=6.4).move_to(ORIGIN)
        # break bars into a pool of small squares, then send them to the frame's cells
        pool = VGroup()
        for bar in bars:
            n = 40
            for k in range(n):
                sq = Square(side_length=0.1, stroke_width=0, fill_color=bar.get_fill_color(), fill_opacity=1)
                sq.move_to(bar.get_bottom() + UP * (k + 0.5) * bar.height / n + RIGHT * random.uniform(-0.5, 0.5) * bar.width)
                pool.add(sq)
        self.remove(bars)
        self.add(pool)
        self.play(FadeOut(VGroup(labels, nums, axis, note)), run_time=0.3)
        picks = random.sample(range(len(cells)), min(len(pool), len(cells)))
        flights = []
        for sq, ci in zip(pool, picks):
            tgt = cells[ci]
            flights.append(sq.animate.move_to(tgt).set_fill(tgt.get_fill_color(), 1).scale_to_fit_width(tgt.width))
        self.play(LaggedStart(*flights, lag_ratio=0.002, run_time=1.6, rate_func=rate_functions.ease_in_out_cubic))
        self.play(FadeIn(cells, lag_ratio=0.0005), FadeIn(border), run_time=1.0)
        self.remove(pool)
        self.wait(1.5)
