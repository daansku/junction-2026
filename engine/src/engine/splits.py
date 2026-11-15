"""Eval / train splits with documented hold-outs.

  eval-v1  : 30 games, difficulties 1/2/3 x 10, seeds 900000+. Frozen.
  train-v1 : >= 2,000 games, seeds 100000+ (disjoint from eval and dev), with hold-outs:
             * no level whose rule set contains a HOLDOUT_PAIRS pair
             * no game whose player colour is in HOLDOUT_PLAYER_COLOURS
  dev      : 10 games, seeds 1000-1009, playtesting only.

Eval games are not filtered; each eval game entry carries a `holdout` tag listing which of
its levels use a held-out rule pair and whether its skin is held out, so analysis can report
seen vs unseen combinations separately (does fine-tuning transfer?).
"""
from __future__ import annotations

from typing import Any

from .render import colors as C

EVAL_SEED_START = 900_000
TRAIN_SEED_START = 100_000
DEV_SEED_START = 1_000

HOLDOUT_PAIRS: list[tuple[str, str]] = [
    ("ice", "teleporters"),
    ("remap", "twin"),
    ("keys_doors", "rotation"),
    ("beacon_goal", "collect_all"),
    ("hazards", "stamina"),
    ("phase_walls", "push_blocks"),
]
HOLDOUT_PLAYER_COLOURS: list[int] = [C.MAROON, C.BROWN]


def holdout_tag(game: dict[str, Any]) -> dict[str, Any]:
    levels = []
    for i, lv in enumerate(game["levels"]):
        rs = set(lv["rules"])
        if any(a in rs and b in rs for a, b in HOLDOUT_PAIRS):
            levels.append(i + 1)
    skin = int(game["skin"]["player"][0]) in HOLDOUT_PLAYER_COLOURS
    return {"levels": levels, "skin": skin}


def is_train_ok(game: dict[str, Any]) -> bool:
    t = holdout_tag(game)
    return not t["levels"] and not t["skin"]


def holdout_doc() -> dict[str, Any]:
    return {"pairs": [list(p) for p in HOLDOUT_PAIRS],
            "player_colours": HOLDOUT_PLAYER_COLOURS,
            "seed_ranges": {"eval": [EVAL_SEED_START, EVAL_SEED_START + 99_999],
                            "train": [TRAIN_SEED_START, EVAL_SEED_START - 1],
                            "dev": [DEV_SEED_START, DEV_SEED_START + 999]}}
