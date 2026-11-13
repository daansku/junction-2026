"""One place that knows which engine is in use (A1's `engine` package or the fake engine).

Game lookup order for (collection, game_id):
  1. real engine + data/collections/<collection>.json exists -> engine.load_game
  2. real engine + id parses as a spec                       -> engine.make_game
  3. fake engine                                             -> fake_engine.load_game
"""
from __future__ import annotations

import json
import logging
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
    eng = _real()
    path = _collection_path(collection)
    if eng is not None and path is not None:
        if hasattr(eng, "list_games"):
            games = eng.list_games(str(path))
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            games = data.get("games", data) if isinstance(data, dict) else data
            games = [_meta_from_describe(eng.load_game(str(path), g["game_id"]).describe(), collection) for g in games]
        return [dict(g, collection=collection) for g in games]
    return fake_engine.list_games(collection)


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


def load_game(game_id: str, collection: Optional[str] = None):
    """Return a fresh Game at its initial state. Raises KeyError if unknown."""
    eng = _real()
    if eng is not None:
        cols = [collection] if collection else collections()
        for c in cols:
            path = _collection_path(c) if c else None
            if path is None:
                continue
            try:
                return eng.load_game(str(path), game_id)
            except Exception:  # noqa: BLE001 - not in this collection
                continue
        try:
            spec = fake_engine.spec_from_game_id(game_id)
            return eng.make_game(eng.GameSpec(seed=spec.seed, difficulty=spec.difficulty, n_levels=spec.n_levels))
        except Exception:  # noqa: BLE001
            pass
    return fake_engine.load_game(collection or "dev", game_id)


def render_png(frame: list[str], scale: int = 8) -> bytes:
    from .render import frame_to_png
    return frame_to_png(frame, scale)
