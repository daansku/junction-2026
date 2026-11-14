"""Rejection-sampling driver (PLAN.md phase 2, A1 Q1; feeds A3-24 and SFT v2).

Two steps around A3's sweep:

1. `pick_games(n)`: train-v1 game ids for the sampling sweep, balanced over difficulty and
   covering every rule. A3 puts them in a sweep yaml and runs strong models (h1 harness).
2. `convert(runs, out)`: turns recorded runs into h1 SFT examples, keeping only the turns of
   levels the model **solved efficiently** (optimal / actions on that level >= min_eff).
   The target is the model's own reply (notes, hypothesis, belief, action), so it carries real
   reasoning, not a template.

The prompt is rebuilt with A3's own `build_parts` + `parts_to_text` (arena), so train ==
inference byte for byte. Only games in train-v1 are accepted: a run on any other game id
(eval-v1, eval-v2, probe-v1, generated) is skipped, whatever its metadata says.
"""
from __future__ import annotations

import io
import json
import re
import tarfile
from collections import Counter
from pathlib import Path
from typing import Iterator

from .. import components as comps
from ..core.game import Game
from ..core.rng import rng_for
from ..core.step import uses_interact
from .common import SOURCE, _games

MIN_EFF = 0.5
_RULE_ID = re.compile("|".join(sorted((n for n in comps.REGISTRY if "_" in n), key=len, reverse=True)))


# ---- 1. games for the sampling sweep ---------------------------------------------------
def pick_games(n: int, seed: int = 0) -> list[str]:
    """Deterministic, difficulty-balanced, rule-covering subset of train-v1."""
    games = list(_games(SOURCE))
    rng = rng_for("rejection", "pick", seed)
    rng.shuffle(games)
    by_d: dict[int, list[dict]] = {}
    for g in games:
        by_d.setdefault(g["spec"]["difficulty"], []).append(g)
    picked, seen_rules = [], Counter()
    ds = sorted(by_d)
    while len(picked) < n and any(by_d.values()):
        for d in ds:
            if not by_d[d] or len(picked) >= n:
                continue
            # prefer the candidate that adds the least-covered rules
            cands = by_d[d][:20]
            best = min(cands, key=lambda g: sum(seen_rules[r] for lv in g["levels"] for r in lv["rules"]))
            by_d[d].remove(best)
            picked.append(best)
            seen_rules.update(r for lv in best["levels"] for r in lv["rules"])
    return [g["game_id"] for g in picked]


# ---- 2. runs -> SFT examples -------------------------------------------------------------
def _iter_runs(src: str | Path) -> Iterator[tuple[dict, list[dict]]]:
    """(meta, steps) from a runs dir (DATA_DIR/runs/<run_id>/...) or a /api/runs/export tar.gz."""
    src = Path(src)
    if src.is_file():
        with tarfile.open(src, "r:*") as tar:
            files: dict[str, dict[str, bytes]] = {}
            for m in tar.getmembers():
                if m.isfile() and m.name.endswith(("meta.json", "steps.jsonl")):
                    run, name = m.name.rsplit("/", 1)
                    f = tar.extractfile(m)
                    if f is not None:
                        files.setdefault(run, {})[name] = f.read()
            for run in sorted(files):
                d = files[run]
                if "meta.json" in d and "steps.jsonl" in d:
                    yield json.loads(d["meta.json"]), [json.loads(l) for l in io.StringIO(d["steps.jsonl"].decode())
                                                       if l.strip()]
        return
    for d in sorted(p for p in src.iterdir() if p.is_dir()):
        mp, sp = d / "meta.json", d / "steps.jsonl"
        if mp.exists() and sp.exists():
            yield (json.loads(mp.read_text(encoding="utf-8")),
                   [json.loads(l) for l in sp.read_text(encoding="utf-8").splitlines() if l.strip()])


def _diff(a: list[str], b: list[str]) -> int:
    return sum(x != y for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def _allowed(game: Game, truth: dict) -> list[str]:
    """What the server offered at that point (sessions._available): GAME_OVER -> RESET only."""
    if truth["state"] == "GAME_OVER":
        return ["RESET"]
    lv = game.levels[min(truth["level"], len(game.levels)) - 1]
    return ["RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4"] + (["ACTION5"] if uses_interact(lv) else [])


def level_segments(steps: list[dict]) -> dict[int, dict]:
    """Per level: step indices whose action was taken on it, actions used, solved?, optimal."""
    seg: dict[int, dict] = {}
    for k in range(1, len(steps)):
        before, after = steps[k - 1]["truth"], steps[k]["truth"]
        lv = before["level"]
        s = seg.setdefault(lv, {"steps": [], "actions": 0, "solved": False,
                                "optimal": before.get("optimal_moves", 0)})
        s["steps"].append(k)
        s["actions"] += 1
        if after["level"] > lv or after["state"] == "WIN":
            s["solved"] = True
    return seg


def run_examples(meta: dict, steps: list[dict], game: Game, min_eff: float = MIN_EFF,
                 drop_bumps: bool = True) -> tuple[list[dict], Counter]:
    from arena.agent_loop import SYSTEM, build_parts       # A3's harness: train == inference
    from arena.dataset import MODES, parts_to_text

    stats: Counter = Counter()
    keep = {}
    for lv, s in level_segments(steps).items():
        eff = s["optimal"] / s["actions"] if s["actions"] else 0.0
        if s["solved"] and eff >= min_eff:
            keep.update({k: (lv, eff) for k in s["steps"]})
            stats["levels_kept"] += 1
        else:
            stats["levels_dropped"] += 1
    out, history = [], []
    for k in range(1, len(steps)):
        prev, cur = steps[k - 1], steps[k]
        if k in keep:
            notes_prev = (prev.get("reasoning") or "") if k > 1 else ""
            reply = {"notes": cur.get("reasoning") or "", "hypothesis": cur.get("hypothesis") or "",
                     "belief": cur.get("belief") or "playing", "action": cur["action"]}
            why = ("empty_notes" if not reply["notes"].strip()
                   else "bump" if drop_bumps and cur["truth"].get("events") == ["bump"]
                   else "rule_id" if _RULE_ID.search(reply["notes"] + " " + reply["hypothesis"])
                   else None)
            if why:
                stats[f"turn_dropped_{why}"] += 1
            else:
                prompt = parts_to_text(build_parts(prev["frame"], notes_prev, history,
                                                   _allowed(game, prev["truth"]), MODES, k))
                lv, eff = keep[k]
                out.append({"messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": prompt},
                                         {"role": "assistant", "content": json.dumps(reply)}],
                            "meta": {"kind": "rejection", "run_id": meta.get("run_id"),
                                     "game_id": meta["game_id"], "level": lv, "step": k,
                                     "level_efficiency": round(eff, 3),
                                     "model_id": (meta.get("player") or {}).get("model_id"),
                                     "harness_version": "h1", "modes": MODES}})
                stats["turns_kept"] += 1
        history.append((cur["action"], _diff(prev["frame"], cur["frame"])))
    return out, stats


def convert(runs: str | Path, out: str | Path, min_eff: float = MIN_EFF, models: list[str] | None = None,
            drop_bumps: bool = True) -> Counter:
    train = {g["game_id"]: g for g in _games(SOURCE)}
    stats: Counter = Counter()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for meta, steps in _iter_runs(runs):
            stats["runs_seen"] += 1
            player = meta.get("player") or {}
            if meta["game_id"] not in train:
                stats["runs_skipped_not_train"] += 1
                continue
            if player.get("kind") != "model" or (models and player.get("model_id") not in models):
                stats["runs_skipped_player"] += 1
                continue
            if meta.get("harness_version") != "h1" or len(steps) < 2:
                stats["runs_skipped_harness"] += 1
                continue
            exs, st = run_examples(meta, steps, Game.from_dict(train[meta["game_id"]]), min_eff, drop_bumps)
            stats.update(st)
            stats["runs_used"] += 1
            for e in exs:
                f.write(json.dumps(e) + "\n")
    return stats
