"""Shared helpers for training-data tasks: game sources, state sampling, text encodings,
answer parsing. Everything is deterministic in (task, seed, index)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any

from .. import components as comps
from ..core.actions import DIRS, Action
from ..core.game import Game, load_collection
from ..core.level import Level, State
from ..core.rng import rng_for
from .. import splits

SOURCE = "train-v1"  # hold-out clean, train seed range, tiers 1-2 only (no eval-v2 rules)
MOVES = [Action.ACTION1, Action.ACTION2, Action.ACTION3, Action.ACTION4]
ACTIONS_HELP = "ACTION1 = up, ACTION2 = down, ACTION3 = left, ACTION4 = right, ACTION5 = interact"


@dataclass
class Sample:
    task: str
    id: str
    prompt: str
    answer: str                     # gold answer text (what goes after "ANSWER:")
    meta: dict[str, Any] = field(default_factory=dict)
    system: str | None = None       # own system prompt (game_turn uses the h1 harness prompt)
    raw_answer: bool = False        # reply is the answer itself (h1 JSON), no "ANSWER:" line

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("system")
        d.pop("raw_answer")
        if self.raw_answer:
            reply = self.answer
        else:
            reply = f"ANSWER: {self.answer}" if "\n" not in self.answer else f"ANSWER:\n{self.answer}"
        d["messages"] = [{"role": "system", "content": self.system or SYSTEM},
                         {"role": "user", "content": self.prompt},
                         {"role": "assistant", "content": reply}]
        return d


SYSTEM = ("You solve puzzles about a grid video game. Think step by step if you like, then end your "
          "reply with a line that starts with 'ANSWER:' followed by the answer in the requested format.")


# ---- sources ---------------------------------------------------------------------------
@lru_cache(maxsize=2)
def _games(collection: str) -> tuple[dict, ...]:
    col = load_collection(collection)
    if col.get("split") == "test" or "eval" in collection:
        raise ValueError(f"refusing to build training tasks from eval collection {collection}")
    games = tuple(g for g in col["games"] if splits.is_train_ok(g))
    tiers = comps.tiers()
    for g in games:  # tier-3 rules are the eval-v2 'unseen' set: must never reach training data
        for lv in g["levels"]:
            if any(tiers.get(r, 0) >= 3 for r in lv["rules"]):
                raise ValueError(f"{g['game_id']} contains a tier-3 rule; not a training source")
    return games


def pick_game(rng, collection: str | None = None) -> Game:
    # SOURCE is read at call time so `engine tasks --collection` can point it elsewhere
    gs = _games(collection or SOURCE)
    return Game.from_dict(gs[rng.randrange(len(gs))])


def collections_dir_root():
    """Repo root (parent of data/collections)."""
    from ..core.game import collections_dir
    return collections_dir().parent.parent


def task_rng(task: str, seed: int, i: int):
    return rng_for("tasks", task, seed, i)


# ---- encodings -----------------------------------------------------------------------
def to_rle(frame: list[str]) -> str:
    """Identical to arena.frames.to_rle (the arena harness text mode), so train == inference."""
    def runs(row: str) -> str:
        out, cur, n = [], row[0], 0
        for ch in row:
            if ch == cur:
                n += 1
            else:
                out.append(f"{cur}x{n}")
                cur, n = ch, 1
        out.append(f"{cur}x{n}")
        return " ".join(out)

    lines, i = [], 0
    while i < len(frame):
        j = i
        while j + 1 < len(frame) and frame[j + 1] == frame[i]:
            j += 1
        lines.append(f"{'r%d' % i if i == j else 'r%d-%d' % (i, j)}: {runs(frame[i])}")
        i = j + 1
    return "\n".join(lines)


_RLE_LINE = re.compile(r"^\s*r(\d+)(?:-(\d+))?\s*:\s*((?:[0-9a-fA-F]x\d+\s*)+)$")


def apply_rle_patch(base: list[str], text: str) -> list[str] | None:
    """Overlay RLE row lines onto `base`. None if any line is malformed or a row is not 64 wide."""
    rows = list(base)
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        m = _RLE_LINE.match(line)
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        row = "".join(c.lower() * int(n) for c, n in (r.split("x") for r in m.group(3).split()))
        if len(row) != 64 or not (0 <= a <= b < 64):
            return None
        for y in range(a, b + 1):
            rows[y] = row
    return rows


def changed_rows_rle(before: list[str], after: list[str]) -> str:
    """Minimal patch: RLE lines for the rows that differ (consecutive identical rows merged)."""
    full = to_rle(after).splitlines()
    out = []
    for line in full:
        tag = line.split(":", 1)[0][1:]
        a, _, b = tag.partition("-")
        a, b = int(a), int(b or a)
        if any(before[y] != after[y] for y in range(a, b + 1)):
            out.append(line)
    return "\n".join(out)


RLE_HELP = ("The screen is a 64x64 grid of colour indices 0-f (hex), written as run-length rows: "
            "'r3-5: 0x2 4x62' means rows 3 to 5 each hold 2 cells of colour 0 then 62 of colour 4.")


# ---- symbolic text grid (planning tasks) -----------------------------------------------
class _Recorder:
    """Stands in for render.Canvas: records which role each logical cell shows (top wins)."""

    def __init__(self, skin):
        self.skin = skin
        self.cells: dict[tuple[int, int], tuple[str, str]] = {}

    def cell(self, p, role, sprite=None, color=None):
        self.cells[tuple(p)] = (role, sprite or self.skin[role][1])

    def color(self, role):
        return self.skin[role][0]


def visible_roles(level: Level, state: State, skin) -> dict[tuple[int, int], tuple[str, str]]:
    rec = _Recorder(skin)
    for c in comps.active(level):
        c.draw(level, state, rec)
    rec.cell(state.pos, "player")
    return rec.cells


def move_dir(a: Action) -> tuple[int, int] | None:
    return DIRS.get(a)


_ANS = re.compile(r"ANSWER\s*:", re.I)
_DECOR = " \t*`'\"_"
MAX_ANSWER_CHARS = 6_000


def extract_answer(output: str) -> str | None:
    """Text after the LAST 'ANSWER:' marker (case-insensitive; markdown like **ANSWER:** ok),
    with code fences and leading/trailing emphasis removed. None if there is no marker or the
    answer itself is absurdly long (reasoning before the marker may be any length)."""
    if not output:
        return None
    last = None
    for last in _ANS.finditer(output):
        pass
    if last is None:
        return None
    ans = output[last.end():]
    lines = [ln for ln in ans.splitlines() if not ln.strip().startswith("```")]
    ans = "\n".join(lines).strip().strip(_DECOR).strip()
    return ans if len(ans) <= MAX_ANSWER_CHARS else None


def first_line(ans: str) -> str:
    """Single-line answers: the first non-empty line, decoration stripped (trailing prose ignored)."""
    for ln in ans.splitlines():
        if ln.strip():
            return ln.strip().strip(_DECOR).strip()
    return ""
