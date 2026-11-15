"""One place that knows which engine is in use (the `engine` package or the fake engine).

Game lookup order for (collection, game_id):
  1. real engine + data/collections/<collection>.json exists -> engine.load_game
  2. real engine + id parses as a spec                       -> engine.make_game
  3. fake engine                                             -> fake_engine.load_game
"""
from __future__ import annotations

import copy
import json
import logging
import threading
from collections import OrderedDict
from functools import lru_cache
from typing import Any, Optional

from . import config, fake_engine

log = logging.getLogger("server.engine")


@lru_cache(maxsize=1)
def _real():
    if config.ENGINE == "fake":
        return None
    try:
        import engine  # type: ignore
        if not hasattr(engine, "make_game"):
            raise ImportError("engine.make_game missing")
        return engine
    except Exception as e:  # noqa: BLE001
        if config.ENGINE == "engine":
            raise
        log.info("real engine unavailable (%s); using fake engine", e)
        return None


def engine_name() -> str:
    return "engine" if _real() else "fake"


def engine_version() -> str:
    eng = _real()
    if eng is None:
        return fake_engine.ENGINE_VERSION
    return str(getattr(eng, "ENGINE_VERSION", getattr(eng, "__version__", "unknown")))


def _collection_path(collection: str):
    p = config.COLLECTIONS_DIR / f"{collection}.json"
    return p if p.exists() else None


def collections() -> list[str]:
    names = sorted(p.stem for p in config.COLLECTIONS_DIR.glob("*.json"))
    return names or ["dev"]


def list_games(collection: str = "dev") -> list[dict[str, Any]]:
    if collection == GENERATED:
        return generated_games()
    eng = _real()
    path = _collection_path(collection)
    if eng is not None and path is not None:
        return [_normalize_meta(m, collection) for m in eng.list_games(str(path))]
    return fake_engine.list_games(collection)


def _normalize_meta(m: dict, collection: str) -> dict:
    """Engine meta -> contracts GameMeta (rules = union, rules_per_level = per level)."""
    rules = m.get("rules", [])
    per_level = m.get("rules_per_level")
    if per_level is None and rules and isinstance(rules[0], list):
        per_level = rules
    per_level = per_level or []
    union = sorted({r for lv in per_level for r in lv}) if per_level else list(rules)
    opt = m.get("optimal_moves")
    return {**m, "collection": collection, "rules": union, "rules_per_level": per_level,
            "optimal_moves_total": m.get("optimal_moves_total", sum(opt) if isinstance(opt, list) else opt)}


def _meta_from_describe(d: dict, collection: str) -> dict:
    levels = d.get("levels", [])
    rules = sorted({r for lv in levels for r in lv.get("rules", [])})
    return {
        "game_id": d["game_id"], "collection": collection, "spec": d.get("spec", {}),
        "engine_version": d.get("engine_version"), "levels_total": d.get("levels_total", len(levels)),
        "difficulty": d.get("spec", {}).get("difficulty"), "rules": rules,
        "rules_per_level": [lv.get("rules", []) for lv in levels],
        "optimal_moves_total": sum(lv.get("optimal_moves", 0) for lv in levels),
    }


# ---------------------------------------------------------------- on-demand generation
GENERATED = "generated"           # pseudo-collection name for games made via POST /games/generate
_GEN_CACHE_MAX = 500
_gen_cache: "OrderedDict[str, Any]" = OrderedDict()
_gen_lock = threading.Lock()
_gen_slots = threading.BoundedSemaphore(2)   # at most 2 generations at once (CPU-bound, ~0.5-2 s each)


def _fresh_copy(game):
    return game.clone() if hasattr(game, "clone") else copy.deepcopy(game)


def generate(seed: int, difficulty: int, n_levels: int):
    """Make (or fetch from cache) a verified game. Raises TimeoutError if the generator is saturated."""
    if not _gen_slots.acquire(timeout=30):
        raise TimeoutError("generator busy")
    try:
        eng = _real()
        if eng is not None:
            game = eng.make_game(eng.GameSpec(seed=seed, difficulty=difficulty, n_levels=n_levels))
        else:
            game = fake_engine.make_game(fake_engine.GameSpec(seed=seed, difficulty=difficulty, n_levels=n_levels))
    finally:
        _gen_slots.release()
    with _gen_lock:
        _gen_cache[game.game_id] = game
        _gen_cache.move_to_end(game.game_id)
        while len(_gen_cache) > _GEN_CACHE_MAX:
            _gen_cache.popitem(last=False)
    return _fresh_copy(game)


def generated_games() -> list[dict[str, Any]]:
    """Metadata of recently generated games, newest first."""
    with _gen_lock:
        games = list(_gen_cache.values())[::-1]
    return [game_meta(g, GENERATED) for g in games]


def game_meta(game, collection: str) -> dict[str, Any]:
    if hasattr(game, "meta"):
        return _normalize_meta(game.meta(), collection)
    return _meta_from_describe(game.describe(), collection)


def load_game(game_id: str, collection: Optional[str] = None):
    """Return a fresh Game at its initial state. Raises KeyError if unknown."""
    with _gen_lock:
        cached = _gen_cache.get(game_id)
    if cached is not None:
        return _fresh_copy(cached)
    if collection == GENERATED:
        collection = None
    eng = _real()
    if eng is not None:
        for c in ([collection] if collection else collections()):
            path = _collection_path(c) if c else None
            if path is None:
                continue
            try:
                return eng.load_game(str(path), game_id)
            except KeyError:
                continue
        # not in a frozen collection: regenerate from the id if it round-trips exactly
        spec = _parse_game_id(game_id)
        if spec is not None:
            try:
                g = eng.make_game(eng.GameSpec(**spec))
                if g.game_id == game_id:
                    return g
            except Exception:  # noqa: BLE001
                pass
    # fake-engine ids (fixtures) stay playable even when the real engine is installed
    return fake_engine.load_game(collection or "dev", game_id)


def _parse_game_id(game_id: str) -> Optional[dict]:
    parts = game_id.split("-")
    if len(parts) != 5:
        return None
    try:
        return {"family": parts[0], "seed": int(parts[1][1:]), "difficulty": int(parts[2][1:]),
                "n_levels": int(parts[3][1:])}
    except ValueError:
        return None


def render_png(frame: list[str], scale: int = 8) -> bytes:
    from .render import frame_to_png
    return frame_to_png(frame, scale)
