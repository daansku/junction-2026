"""S2 The gap: h1 board, then h2 board ("run the way labs benchmark them"). See SCRIPT.md S2.

Numbers come from cache/derived/leaderboard.json (live /api/derived/leaderboard.json).
Ranking is completion first (human decision Sat ~23:45, coordination/DECISIONS.md): bars show games won, ordered by
games won, then levels solved, then efficiency; the efficiency score is the small grey second number.
The narration line for h2 is still open (SCRIPT.md); the chart shows whatever the data says.
"""
from __future__ import annotations

from manim import (
    Group,
    DOWN, LEFT, RIGHT, UP, DashedLine, FadeIn, FadeOut, GrowFromEdge, LaggedStart, Line,
    Rectangle, Scene, Text, VGroup,
)

from common import (
    Narration,
    ACCENT, LINE, LINE_STRONG, MONO, PLACEHOLDER, SANS, TEXT_1, TEXT_2, TEXT_3, load_json,
)

BAR_COLOR = "#3987e5"     # DESIGN.md chart slot 1
HUMAN_COLOR = TEXT_2


def rows_for(lb, harness: str | None, collections: list[str]):
    out = []
    for r in lb["rows"]:
        if r["kind"] == "model" and r["harness_version"] == harness and r["collection"] in collections:
            out.append(r)
    out.sort(key=completion_key)
    return out


def completion_key(r) -> tuple:
    return (-(r.get("game_win_rate") or 0), -(r.get("level_solve_rate") or 0), -(r.get("score") or 0))


def human_row(lb, collection: str):
    for r in lb["rows"]:
        if r["kind"] == "human" and r["collection"] == collection:
            return r
    return None


def clean_name(r) -> str:
    n = r["display_name"]
    n = n.replace(" fine-tuned on train-v1 (ours)", " SFT v1 (ours)")
    for junk in (" [eval-v1]", " [eval-v2]", " [dev]", " (Verda)", " (preview)", " (Modal)"):
        n = n.replace(junk, "")
    if r["collection"] == "eval-v2":
        n += "  · eval-v2"
    return n


class S2Gap(Scene):
    def board(self, title: str, subtitle: str, rows, human, width: float = 5.6):
        """Horizontal bar board (bar = share of games won); returns (group, bars, reference)."""
        g = VGroup()
        head = Text(title, font=SANS, font_size=26, color=TEXT_1, weight="MEDIUM")
        sub = Text(subtitle, font=MONO, font_size=14, color=TEXT_3).next_to(head, DOWN, aligned_edge=LEFT, buff=0.1)
        g.add(head, sub)
        name_w = 2.6
        y = sub.get_bottom()[1] - 0.45
        x_left = head.get_left()[0] + name_w
        bars = []
        items = [(clean_name(r), r, BAR_COLOR) for r in rows]
        if human:
            items.append(("humans, first attempt", human, HUMAN_COLOR))
        items.sort(key=lambda t: completion_key(t[1]))
        for name, row, color in items:
            won = row.get("game_win_rate") or 0.0
            lab = Text(name, font=SANS, font_size=16, color=TEXT_2 if color == BAR_COLOR else TEXT_1)
            lab.move_to([head.get_left()[0] + lab.width / 2, y, 0])
            bar = Rectangle(width=max(0.02, width * won), height=0.3, fill_color=color, fill_opacity=1, stroke_width=0)
            bar.move_to([x_left + bar.width / 2, y, 0])
            won_t = Text(f"{won * 100:.0f}% won", font=MONO, font_size=15, color=TEXT_1)
            eff_t = Text(f"eff {row['score']:.2f}", font=MONO, font_size=12, color=TEXT_3)
            num = VGroup(won_t, eff_t).arrange(RIGHT, buff=0.12, aligned_edge=DOWN).next_to(bar, RIGHT, buff=0.1)
            g.add(lab)
            bars.append((bar, num))
            y -= 0.48
        ref = DashedLine([x_left + width, sub.get_bottom()[1] - 0.2, 0], [x_left + width, y + 0.2, 0],
                         stroke_color=ACCENT, stroke_width=2, dash_length=0.08)
        ref_lab = Text("optimal play wins 100%", font=MONO, font_size=14, color=ACCENT).next_to(ref, UP, buff=0.05)
        base = Line([x_left, sub.get_bottom()[1] - 0.2, 0], [x_left, y + 0.2, 0], stroke_color=LINE_STRONG, stroke_width=1)
        g.add(base)
        return g, bars, (ref, ref_lab)

    def construct(self):
        lb = load_json("derived/leaderboard.json")
        b1_rows = rows_for(lb, "h1", ["eval-v1"])
        b2_rows = rows_for(lb, "h2", ["eval-v1", "eval-v2"])

        g1, bars1, ref1 = self.board("Games nobody has seen", "h1 harness · eval-v1 · games won",
                                     b1_rows, human_row(lb, "eval-v1"))
        all1 = VGroup(g1, *[b for b, _ in bars1], *[n for _, n in bars1], *ref1)
        all1.move_to([0, 0.1, 0])
        vo = Narration(self, "S2")
        vo.cue(0, delay=0.3)
        self.play(FadeIn(g1), FadeIn(VGroup(*ref1)), run_time=0.6)
        self.play(LaggedStart(*[GrowFromEdge(b, LEFT) for b, _ in bars1], lag_ratio=0.12, run_time=1.6))
        self.play(LaggedStart(*[FadeIn(n) for _, n in bars1], lag_ratio=0.06), run_time=0.6)
        tag = Text("numbers not locked", font=MONO, font_size=14, color=PLACEHOLDER).to_corner(DOWN + RIGHT, buff=0.3)
        self.add(tag)
        self.wait(2.0)

        # ---- board 2: run the lab way ----
        vo.cue(1, delay=0.2)
        self.play(all1.animate.scale(0.62).to_edge(LEFT, buff=0.4), run_time=0.8)
        g2, bars2, ref2 = self.board("Run the way labs benchmark them",
                                     "h2 harness · full conversation · max reasoning effort",
                                     b2_rows, human_row(lb, "eval-v2"))
        all2 = VGroup(g2, *[b for b, _ in bars2], *[n for _, n in bars2], *ref2)
        all2.scale(0.62).to_edge(RIGHT, buff=0.4).align_to(all1, UP)
        self.play(FadeIn(g2), FadeIn(VGroup(*ref2)), run_time=0.6)
        self.play(LaggedStart(*[GrowFromEdge(b, LEFT) for b, _ in bars2], lag_ratio=0.12, run_time=1.4))
        self.play(LaggedStart(*[FadeIn(n) for _, n in bars2], lag_ratio=0.06), run_time=0.6)
        self.wait(2.0)

        # ---- the gap to the reference: bracket on the best model of board 2 ----
        vo.cue(2, delay=0.0)
        if bars2:
            best_bar, _ = bars2[0]
            ref_line = ref2[0]
            gap = Line(best_bar.get_right(), [ref_line.get_x(), best_bar.get_y(), 0], stroke_color=ACCENT, stroke_width=4)
            gap_lab = Text("gap", font=MONO, font_size=16, color=ACCENT).next_to(gap, UP, buff=0.05)
            self.play(FadeIn(gap), FadeIn(gap_lab), run_time=0.5)
        self.wait(2.0)
        vo.finish(tail=0.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)
