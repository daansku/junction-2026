"""S0 Hook: break one agent; two real failures up close (the frame turns the failure colour);
zoom out to many agents moving and failing; the shards stack into the failure-mode chart and
morph straight into a game frame. See video/SCRIPT.md S0.

Render draft (from video/scenes):  ../.venv/Scripts/manim.exe -ql --media_dir ../media s0_hook.py S0Hook
"""
from __future__ import annotations

import math
import random

from manim import (
    DOWN, LEFT, ORIGIN, RIGHT, UP, AnimationGroup, FadeIn, FadeOut, Group, LaggedStart,
    Rectangle, Scene, Square, Text, VGroup, rate_functions, smooth,
)

from common import (
    Narration,
    CACHE, FAILURE_MODES, LINE_STRONG, MONO, PALETTE, SANS, TEXT_1, TEXT_2, TEXT_3,
    agent_sprite, frame_cells, frame_image, framed, load_json, set_frame,
)

random.seed(7)
NEMOTRON = "20261114T015741-02f65e44"   # hazards level, bumps the same wall from step 16
KIMI = "20261114T015741-3858885a"       # one_way level, resets at step 123
SHARDS_PER_SIDE = 4                     # each failed tile breaks into 4x4 shards


def shards_for(mob, color: str, n: int = SHARDS_PER_SIDE) -> VGroup:
    s = mob.height / n
    g = VGroup()
    for i in range(n):
        for j in range(n):
            sq = Square(side_length=s * 0.9, stroke_width=0, fill_color=color, fill_opacity=1)
            sq.move_to(mob.get_corner(UP + LEFT) + RIGHT * (j + 0.5) * s + DOWN * (i + 0.5) * s)
            g.add(sq)
    return g


def two_line(text: str, width: float, size: int) -> Text:
    t = Text(text, font=SANS, font_size=size, color=TEXT_2)
    if t.width <= width:
        return t
    w = text.split(" ")
    m = len(w) // 2
    return Text(" ".join(w[:m]) + "\n" + " ".join(w[m:]), font=SANS, font_size=size, color=TEXT_2, line_spacing=0.8)


class S0Hook(Scene):
    # ------------------------------------------------------------------ close-up replay
    def closeup(self, run_id: str, first: int, last: int, mode_i: int, line_dur: float, caption_step: int):
        steps = load_json(f"steps/{run_id}.json")
        mode, text, color = FAILURE_MODES[mode_i]
        img = frame_image(steps[first]["frame"], height=5.4).shift(UP * 0.35)
        border = framed(img)
        hyp = steps[caption_step].get("hypothesis") or ""
        quote = Text(f"model: “{hyp[:64]}{'…' if len(hyp) > 64 else ''}”", font=MONO, font_size=17, color=TEXT_2)
        quote.next_to(img, DOWN, buff=0.25)
        counter = Text("", font=MONO, font_size=16, color=TEXT_3)
        self.play(FadeIn(Group(img, border), scale=0.95), run_time=0.5)
        self.play(FadeIn(quote, shift=UP * 0.1), run_time=0.3)
        # spread the replay over the spoken line (the tint and name land at its end)
        step_time = min(0.35, max(0.1, (line_dur - 1.4) / (last - first)))
        for k in range(first + 1, last + 1):
            st = steps[k]
            set_frame(img, st["frame"])
            ev = (st.get("truth") or {}).get("events") or []
            new_counter = Text(f"step {st['i']:>3}  {st['action'] or ''}", font=MONO, font_size=16, color=TEXT_3)
            new_counter.next_to(img, UP, buff=0.12).align_to(img, LEFT)
            self.remove(counter)
            counter = new_counter
            self.add(counter)
            if "bump" in ev or "reset" in ev:
                flash = framed(img).set_stroke(color, width=6)
                self.add(flash)
                self.wait(step_time)
                self.remove(flash)
            else:
                self.wait(step_time)
        # the failure takes its colour: tint the frame, name the mode
        tint = Rectangle(width=img.width, height=img.height, fill_color=color, fill_opacity=0, stroke_width=0).move_to(img)
        name = Text(text, font=SANS, font_size=30, color=color).move_to(quote)
        self.add(tint)
        self.play(tint.animate.set_fill(opacity=0.85), FadeOut(quote), FadeIn(name, shift=UP * 0.1), run_time=1.0)
        self.wait(0.2)
        shards = shards_for(img, color)
        self.remove(img, tint)
        self.add(shards)
        self.play(FadeOut(VGroup(border, counter)), shards.animate.scale(1.08), run_time=0.3)
        return shards, name

    def construct(self):
        rules = load_json("derived/rules.json")
        counts = {m["mode"]: m["count"] for m in rules["failure_modes"]}
        vo = Narration(self, "S0")
        vo.cue(0, delay=0.4)

        # ---------------- 0:00 one agent breaks ----------------
        floor = Rectangle(width=9, height=0.06, fill_color=LINE_STRONG, fill_opacity=1, stroke_width=0).shift(DOWN * 0.8)
        wall = Rectangle(width=0.35, height=2.2, fill_color=PALETTE[5], fill_opacity=1, stroke_width=0)
        wall.next_to(floor, UP, buff=0).shift(RIGHT * 2.5)
        agent = agent_sprite(PALETTE[15], unit=0.22).next_to(floor, UP, buff=0).shift(LEFT * 3)
        self.play(FadeIn(floor), FadeIn(wall), FadeIn(agent, shift=UP * 0.2), run_time=0.8)
        for _ in range(3):
            self.play(agent.animate.shift(RIGHT * 1.45), run_time=0.35, rate_func=smooth)
        self.play(agent.animate.shift(RIGHT * 0.1), run_time=0.12, rate_func=rate_functions.there_and_back)
        red = FAILURE_MODES[0][2]
        self.play(agent.animate.set_fill(red), run_time=0.4)
        cx = agent.get_x()
        left = VGroup(*[p for p in agent if p.get_x() < cx])
        right = VGroup(*[p for p in agent if p.get_x() >= cx])
        self.play(
            left.animate.shift(LEFT * 0.5 + DOWN * 0.15).rotate(0.35),
            right.animate.shift(RIGHT * 0.15 + UP * 0.1).rotate(-0.5),
            run_time=0.7, rate_func=rate_functions.ease_out_cubic,
        )
        self.wait(0.8)
        self.play(FadeOut(VGroup(floor, wall, left, right)), run_time=0.4)

        # ---------------- two real failures up close ----------------
        vo.cue(1, delay=0.0)
        c1, n1 = self.closeup(NEMOTRON, 14, 27, 0, vo.dur(1), 18)
        self.play(FadeOut(n1), c1.animate.scale(0.35).to_edge(LEFT, buff=0.6).shift(UP * 2.2), run_time=0.6)
        vo.cue(2, delay=0.0)
        c2, n2 = self.closeup(KIMI, 104, 123, 1, vo.dur(2), 115)
        vo.cue(3, delay=0.0)  # "now break thousands" starts as the second close-up shrinks into the grid
        self.play(FadeOut(n2), c2.animate.scale(0.35).next_to(c1, RIGHT, buff=0.3), run_time=0.6)

        # ---------------- zoom out: many agents moving, then failing ----------------
        srcs = [load_json(f"wall/{p.name}") for p in sorted((CACHE / "wall").glob("*.json"))]
        cols, rows = 16, 9
        tile_h, gap = 0.72, 0.1
        pitch = tile_h + gap
        positions = [((c - (cols - 1) / 2) * pitch, ((rows - 1) / 2 - r) * pitch) for r in range(rows) for c in range(cols)]
        # tile modes: shard count per mode proportional to log10(count), so the stacked columns
        # are a log-scale chart of the real counts
        logs = [math.log10(max(counts.get(m, 1), 1)) for m, _, _ in FAILURE_MODES]
        n_tiles = len(positions)
        quota = [round(n_tiles * l / sum(logs)) for l in logs]
        quota[0] += n_tiles - sum(quota)
        modes = [i for i, q in enumerate(quota) for _ in range(q)]
        modes[1], modes[quota[0]] = 1, 0      # first two slots are the close-ups (red, orange); swap keeps the quotas
        rest = modes[2:]
        random.shuffle(rest)
        modes = modes[:2] + rest

        tiles = Group()
        players = []
        for k, (x, y) in enumerate(positions[2:], start=2):
            src = srcs[k % len(srcs)]
            fr = src["frames"]
            img = frame_image(fr[0]["frame"], height=tile_h).move_to([x, y, 0])
            img.frames = [f["frame"] for f in fr]
            img.phase = random.random() * len(fr)
            tiles.add(img)
            players.append(img)
        zoom = 2.6
        whole = Group(tiles)
        whole.scale(zoom, about_point=ORIGIN)
        # close-up shard groups go into the first two grid slots
        slot0 = [positions[0][0] * zoom, positions[0][1] * zoom, 0]
        slot1 = [positions[1][0] * zoom, positions[1][1] * zoom, 0]

        t_acc = {"t": 0.0}

        def step_frames(m, dt):
            t_acc["t"] += dt
            for p in players:
                idx = int(p.phase + t_acc["t"] * 6) % len(p.frames)
                set_frame(p, p.frames[idx])

        tiles.add_updater(step_frames)
        self.play(
            FadeIn(tiles),
            c1.animate.scale_to_fit_height(tile_h * zoom * 0.95).move_to(slot0),
            c2.animate.scale_to_fit_height(tile_h * zoom * 0.95).move_to(slot1),
            run_time=0.8,
        )
        self.play(Group(tiles, c1, c2).animate.scale(1 / zoom, about_point=ORIGIN), run_time=2.4,
                  rate_func=rate_functions.ease_in_out_cubic)
        self.wait(0.4)

        # each tile turns its failure colour, then breaks into shards
        all_shards = [None] * n_tiles
        all_shards[0], all_shards[1] = c1, c2
        tint_anims, tints = [], []
        order = list(range(2, n_tiles))
        random.shuffle(order)
        for k in order:
            p = tiles[k - 2]
            color = FAILURE_MODES[modes[k]][2]
            t = Rectangle(width=p.width, height=p.height, fill_color=color, fill_opacity=0, stroke_width=0).move_to(p)
            tints.append((k, t))
            tint_anims.append(t.animate.set_fill(opacity=0.85))
        self.add(*[t for _, t in tints])
        vo.cue(4, delay=0.0)  # "the failures stop being noise" lands as the tiles take their colours
        self.play(LaggedStart(*tint_anims, lag_ratio=0.015, run_time=2.0))
        tiles.clear_updaters()
        for k, t in tints:
            all_shards[k] = shards_for(tiles[k - 2], FAILURE_MODES[modes[k]][2])
        self.remove(tiles, *[t for _, t in tints])
        self.add(*all_shards[2:])
        self.wait(0.1)

        # ---------------- shards stack into the failure-mode chart (no solid bars) ----------------
        base_y = -2.5
        chart_w = 11.4
        per_row = 8
        tallest = max(quota) * SHARDS_PER_SIDE ** 2 / per_row
        s = 4.6 / tallest                       # shard pitch so the tallest column is 4.6 high
        col_w = s * per_row
        moves, labels, nums = [], VGroup(), VGroup()
        stacks = [[] for _ in FAILURE_MODES]
        for k in range(n_tiles):
            stacks[modes[k]].extend(list(all_shards[k]))
        for i, (mode, text, color) in enumerate(FAILURE_MODES):
            x = (i - (len(FAILURE_MODES) - 1) / 2) * (chart_w / len(FAILURE_MODES))
            sh = stacks[i]
            for j, sq in enumerate(sh):
                rr, cc = divmod(j, per_row)
                target = [x - col_w / 2 + (cc + 0.5) * s, base_y + (rr + 0.5) * s, 0]
                moves.append(sq.animate.move_to(target).scale_to_fit_width(s * 0.86))
            top = base_y + math.ceil(len(sh) / per_row) * s
            lab = two_line(text, 1.75, 17).move_to([x, base_y - 0.45, 0])
            labels.add(lab)
            nums.add(Text(f"{counts.get(mode, 0):,}", font=MONO, font_size=20, color=TEXT_1).move_to([x, top + 0.25, 0]))
        axis = Rectangle(width=chart_w + 0.4, height=0.03, fill_color=LINE_STRONG, fill_opacity=1, stroke_width=0).move_to([0, base_y - 0.05, 0])
        self.play(LaggedStart(*moves, lag_ratio=0.0006, run_time=2.4, rate_func=rate_functions.ease_in_out_cubic))
        note = Text("failure-mode counts, all model runs (log scale)", font=MONO, font_size=14, color=TEXT_3).to_corner(UP + LEFT, buff=0.5)
        self.play(FadeIn(axis), LaggedStart(*[FadeIn(l, shift=UP * 0.1) for l in labels], lag_ratio=0.1),
                  LaggedStart(*[FadeIn(n) for n in nums], lag_ratio=0.1), FadeIn(note), run_time=1.0)
        self.wait(0.7)

        # ---------------- the stacked shards morph straight into a game frame ----------------
        steps = load_json(f"steps/{NEMOTRON}.json")
        cells = list(frame_cells(steps[16]["frame"], size=6.4))
        shards = [sq for st in stacks for sq in st]
        shards.sort(key=lambda m: (round(m.get_x(), 2), m.get_y()))
        cells.sort(key=lambda m: (round(m.get_x(), 2), m.get_y()))
        border = framed(Square(side_length=6.4))
        vo.cue(5, delay=0.0)
        self.play(FadeOut(VGroup(labels, nums, axis, note)), run_time=0.4)
        morphs = []
        for sq, cell in zip(shards, cells):
            morphs.append(sq.animate.move_to(cell).set_fill(cell.get_fill_color(), 1).scale_to_fit_width(cell.width * 1.02))
        extra = shards[len(cells):]
        self.play(LaggedStart(*morphs, lag_ratio=0.0004, run_time=2.4, rate_func=rate_functions.ease_in_out_cubic),
                  *[FadeOut(e, scale=0.3) for e in extra])
        missing = VGroup(*cells[len(shards):])
        self.play(FadeIn(border), FadeIn(missing), run_time=0.6)
        self.wait(1.0)
        vo.finish()
