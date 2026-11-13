"""Server settings from environment variables."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _home() -> Path:
    try:
        return Path.home()
    except RuntimeError:  # some make/CI environments strip HOME and USERPROFILE
        import tempfile
        return Path(os.environ.get("HOME") or tempfile.gettempdir())


DATA_DIR = Path(os.environ.get("DATA_DIR") or str(_home() / "junction-data")).expanduser()
RUNS_DIR = DATA_DIR / "runs"
DERIVED_DIR = Path(os.environ.get("DERIVED_DIR", str(REPO_ROOT / "data" / "derived")))
PUBLISHED_DIR = REPO_ROOT / "data" / "published"
FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"
COLLECTIONS_DIR = REPO_ROOT / "data" / "collections"
WEB_DIST = Path(os.environ.get("WEB_DIST", str(REPO_ROOT / "web" / "dist")))

# auto: use A1's `engine` package if importable, else the fake engine. fake | engine force one.
ENGINE = os.environ.get("SERVER_ENGINE", "auto")
PUBLISHED_MODE = _bool("PUBLISHED_MODE")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
SESSION_IDLE_S = int(os.environ.get("SESSION_IDLE_S", "3600"))
MAX_ACTIONS_PER_SESSION = int(os.environ.get("MAX_ACTIONS_PER_SESSION", "5000"))
