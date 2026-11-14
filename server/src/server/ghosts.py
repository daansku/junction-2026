"""Ghost race data: per-level step slices of recorded runs, plus a synthesized optimal ghost.

The browser asks for one level of one game and gets small slices instead of whole multi-MB steps.jsonl files.
Finished runs are immutable, so their parsed slices are cached by (run_id, steps mtime).
"""
from __future__ import annotations

import json
import threading
from collections import OrderedDict
from typing import Any, Optional

from . import engine_adapter
from .recorder import Recorder

_CACHE_MAX = 256
_cache: "OrderedDict[tuple, dict[int, dict]]" = OrderedDict()
_lock = threading.Lock()


def _clip(s: Optional[str], n: int) -> Optional[str]:
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n] + "…"


def _slim(step: dict, frames: bool, reasoning_chars: int) -> dict:
    t = step.get("truth") or {}
    out = {"i": step.get("i"), "action": step.get("action"), "events": t.get("events", []),
           "state": t.get("state"), "hypothesis": _clip(step.get("hypothesis"), 600),
           "belief": step.get("belief")}
    if reasoning_chars:
        out["reasoning"] = _clip(step.get("reasoning"), reasoning_chars)
    if frames:
        out["frame"] = step.get("frame")
    return out


def _level_slices(recorder: Recorder, run_id: str) -> dict[int, dict]:
    """{level: {"start": step dict (frame at level start), "steps": [...], "solved": bool}} for one run."""
    path = recorder.run_dir(run_id) / "steps.jsonl"
    key = (run_id, path.stat().st_mtime_ns)
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return hit
    levels: dict[int, dict] = {}
    prev: Optional[dict] = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                st = json.loads(line)
            except json.JSONDecodeError:
                break  # torn last line
            lv = int((st.get("truth") or {}).get("level", 1))
            if st.get("action") is None:          # initial frame
                levels.setdefault(lv, {"start": st, "steps": [], "solved": False})
            else:
                prev_lv = int((prev.get("truth") or {}).get("level", 1)) if prev else lv
                # the step that completes a level belongs to that level; its frame shows the next level
                owner = prev_lv
                slot = levels.setdefault(owner, {"start": prev or st, "steps": [], "solved": False})
                slot["steps"].append(st)
                if lv > prev_lv or (st.get("truth") or {}).get("state") == "WIN":
                    slot["solved"] = True
                    levels.setdefault(lv, {"start": st, "steps": [], "solved": False})
            prev = st
    with _lock:
        _cache[key] = levels
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return levels


def optimal_ghost(game_id: str, level: int, collection: Optional[str], frames: bool) -> Optional[dict]:
    game = engine_adapter.load_game(game_id, collection)
    desc = game.describe()
    if not 1 <= level <= desc["levels_total"]:
        return None
    start = jump_to_level(game, level, desc)
    path = desc["levels"][level - 1]["optimal_path"]
    steps = []
    for i, a in enumerate(path, start=1):
        fr = list(game.step(a))
        t = game.truth()
        steps.append({"i": i, "action": a, "events": t.get("events", []), "state": t.get("state"),
                      "hypothesis": None, "belief": None, **({"frame": fr} if frames else {})})
    return {"run_id": None, "player": {"kind": "baseline", "name": "optimal", "model_id": None},
            "solved": True, "actions": len(path), "start_frame": start if frames else None, "steps": steps}


def jump_to_level(game, level: int, desc: Optional[dict] = None) -> list[str]:
    """Put a fresh game at the start of `level`; returns the frame. Uses engine goto_level when available."""
    if level <= 1:
        return list(game.reset())
    if hasattr(game, "goto_level"):
        return list(game.goto_level(level))
    desc = desc or game.describe()
    game.reset()
    frame = list(game.frame())
    for lv in desc["levels"][: level - 1]:
        for a in lv["optimal_path"]:
            frame = list(game.step(a))
    return frame


def ghosts(recorder: Recorder, game_id: str, level: int, limit: int = 3, kinds: tuple = ("model",),
           include_optimal: bool = True, frames: bool = True, reasoning_chars: int = 0,
           collection: Optional[str] = None) -> dict:
    candidates = []
    for m in recorder.list(game_id=game_id, limit=10**6):
        if not m.get("ended_at") or m.get("player", {}).get("kind") not in kinds or m.get("start_level"):
            continue
        try:
            sl = _level_slices(recorder, m["run_id"]).get(level)
        except (FileNotFoundError, KeyError):
            continue
        if not sl or not sl["steps"]:
            continue
        candidates.append((m, sl))
    # best first: solved, then fewer actions on the level, then newer
    candidates.sort(key=lambda c: (not c[1]["solved"], len(c[1]["steps"]), c[0].get("started_at", "")))
    seen_players: set = set()
    out = []
    for m, sl in candidates:
        p = m["player"]
        who = (p.get("model_id") or p.get("name"), p.get("effort"))
        if who in seen_players:  # one ghost per model, its best attempt
            continue
        seen_players.add(who)
        out.append({"run_id": m["run_id"],
                    "player": {"kind": p.get("kind"), "name": p.get("name"), "model_id": p.get("model_id"),
                               "provider": p.get("provider"), "effort": p.get("effort")},
                    "solved": sl["solved"], "actions": len(sl["steps"]),
                    "first_step": sl["steps"][0].get("i"),
                    "start_frame": sl["start"].get("frame") if frames else None,
                    "steps": [_slim(s, frames, reasoning_chars) for s in sl["steps"]]})
        if len(out) >= limit:
            break
    opt = optimal_ghost(game_id, level, collection, frames) if include_optimal else None
    return {"game_id": game_id, "level": level, "optimal": opt, "ghosts": out}
