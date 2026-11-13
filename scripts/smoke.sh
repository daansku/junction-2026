#!/usr/bin/env bash
# Smoke test: starts a throwaway local server unless API_URL is set, then plays a game to a win.
#   scripts/smoke.sh                       # local server on :8765 with a temp DATA_DIR
#   API_URL=https://... scripts/smoke.sh   # against a running server (e.g. the shared one)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; elif [ -x .venv/Scripts/python ]; then PY=.venv/Scripts/python; else PY=python; fi
if [ -n "${API_URL:-}" ]; then
  exec "$PY" scripts/smoke.py --api "$API_URL"
fi
exec "$PY" scripts/smoke.py --local
