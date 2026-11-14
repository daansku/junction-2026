"""Training data for post-training (PLAN.md phase 2, §3.3; A1-20..A1-23).

    from engine.tasks import generate, reward
    for s in generate("rule_effect", n=100, seed=0): ...
    r = reward(sample_dict, model_reply)          # float in [0, 1]

CLI: python -m engine tasks --task all --n 1000 --seed 0 --out data/tasks/aux-s0.jsonl
Sources are train-v1 games only (train seed range, hold-outs removed, no tier-3 rules).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from .auxtasks import TASKS
from .common import SYSTEM, Sample
from .rewards import RAW_TASKS, episode_score, reward

# `--task all`: the single-turn tasks that need only the engine. game_turn needs arena (A3's
# harness prompt) at generation time, so it is requested by name.
DEFAULT_ALL = [t for t in TASKS if t not in RAW_TASKS]


def generate(task: str, n: int, seed: int = 0, max_skips: int = 1000) -> Iterator[Sample]:
    make = TASKS[task][0]
    got = skips = i = 0
    while got < n:
        s = make(seed, i)
        i += 1
        if s is None:
            skips += 1
            if skips > max_skips:
                raise RuntimeError(f"{task}: too many failed samples")
            continue
        got += 1
        yield s


def write_jsonl(path: str | Path, tasks: list[str], n: int, seed: int = 0) -> dict[str, int]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for t in tasks:
            counts[t] = 0
            for s in generate(t, n, seed):
                f.write(json.dumps(s.to_dict()) + "\n")
                counts[t] += 1
    return counts


__all__ = ["TASKS", "DEFAULT_ALL", "RAW_TASKS", "SYSTEM", "Sample", "generate", "reward", "episode_score", "write_jsonl"]
