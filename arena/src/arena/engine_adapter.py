"""Find a local engine implementing contracts/engine_api.py, for offline work (dataset building).

Order: the `engine` package -> `server.fake_engine` -> arena's MockGame-backed shim.
Sweeps never use this; they go through the server.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .frames import _repo_root


def _try_path(pkg_dir: Path):
    p = str(pkg_dir)
    if pkg_dir.exists() and p not in sys.path:
        sys.path.insert(0, p)


def load_engine():
    """Returns (module, name). Module has make_game(spec), load_game(collection, game_id), GameSpec."""
    root = _repo_root()
    try:
        import engine  # noqa: F401
        if hasattr(engine, "make_game"):
            return engine, "engine"
    except ImportError:
        pass
    _try_path(root / "engine" / "src")
    try:
        import engine  # noqa: F811
        if hasattr(engine, "make_game"):
            return engine, "engine"
    except ImportError:
        pass
    _try_path(root / "server" / "src")
    try:
        from server import fake_engine
        return fake_engine, "server.fake_engine"
    except ImportError:
        pass
    from . import mock_game
    return mock_game, "arena.mock_game"
