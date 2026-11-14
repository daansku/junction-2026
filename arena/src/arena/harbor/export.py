"""Export games as Harbor tasks (one directory per game), for the AfterQuery judging harness.

    python -m arena harbor-export --collection eval-v1 --out harbor/eval-v1 [--first 10]
    harbor run -p harbor/eval-v1 -a oracle                       # reference run (optimal play)
    harbor run -p harbor/eval-v1 -a nop                          # do-nothing baseline -> 0
    harbor run -p harbor/eval-v1 -a opencode -m <provider/model> # frontier agent

Layout per task (Harbor task format, schema 1.1, modelled on harbor's examples/tasks/hello-mcp):
  task.toml                 MCP server declared as [[environment.mcp_servers]] (streamable-http)
  instruction.md            what the agent is told: tools, actions, "find the goal", scoring
  environment/Dockerfile    agent container (plain ubuntu; no game code in it)
  environment/docker-compose.yaml   + `game` sidecar service
  environment/game/         sidecar image: engine + arena sidecar + one-game collection + token
  tests/test.sh             verifier: GET /score?token= -> /logs/verifier/reward.json + reward.txt
  solution/solve.sh         oracle: replays the optimal path through MCP
"""
from __future__ import annotations

import json
import secrets
import shutil
from pathlib import Path

from ..frames import _repo_root

SIDECAR_FILES = ["__init__.py", "frames.py", "engine_adapter.py", "mock_game.py", "harbor/__init__.py",
                 "harbor/sidecar.py"]


def _task_toml(name: str, agent_timeout: int) -> str:
    return f'''schema_version = "1.1"

[task]
name = "junction-arena/{name}"
description = "Unknown grid game; discover the rules by acting; finish every level in few actions."
authors = []
keywords = ["rule-discovery", "games", "arc-agi-3-style", "mcp"]

[metadata]

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = {float(agent_timeout)}

[environment]
build_timeout_sec = 900.0
cpus = 1
memory_mb = 2048
storage_mb = 4096
gpus = 0
[[environment.mcp_servers]]
name = "game"
transport = "streamable-http"
url = "http://game:8000/mcp"
args = []

[verifier.env]

[environment.env]

[solution.env]
'''


INSTRUCTION = """# Play an unknown game

An MCP server named `game` (http://game:8000/mcp) runs a video game you have never seen. It has two tools:

- `observe()` shows the current screen (free).
- `act(action, note?)` takes one action and shows the new screen. Actions: `ACTION1` up, `ACTION2` down,
  `ACTION3` left, `ACTION4` right, `ACTION5` interact, `RESET` restart the current level.

The screen is a 64x64 image, also given as a text grid (one hex digit 0-f per cell = colour index, row 0 at the top).
Nobody tells you the goal, the rules or what the colours mean: work them out by acting and watching what changes.
The game has several levels; later levels may add new mechanics.

**Goal:** finish as many levels as you can, using as few actions as possible. Every action (including RESET) counts
against your score; looking with `observe()` is free. When you have finished the game, or are certain you cannot
make more progress, stop. Do not look for the score anywhere else: only playing through the `game` tools counts.
"""

TEST_SH = """#!/bin/bash
# Verifier: ask the game sidecar for the score (token known only to the verifier) and write the reward.
set -u
mkdir -p /logs/verifier
python3 - <<'EOF'
import json, urllib.request
url = "http://game:8000/score?token=__TOKEN__"
try:
    s = json.load(urllib.request.urlopen(url, timeout=30))
except Exception as e:
    s = {"reward": 0.0, "error": str(e)}
reward = float(s.get("reward", 0.0))
metrics = {"reward": reward}
for k in ("levels_solved", "levels_total", "actions", "invalid_actions"):
    if isinstance(s.get(k), (int, float)):
        metrics[k] = s[k]
metrics["won"] = 1 if s.get("won") else 0
open("/logs/verifier/reward.json", "w").write(json.dumps(metrics))
open("/logs/verifier/reward.txt", "w").write(str(reward))
open("/logs/verifier/score_detail.json", "w").write(json.dumps(s))
print(json.dumps(s))
EOF
"""

SOLVE_SH = """#!/bin/bash
# Oracle (reference run): replay the engine's optimal path through the game's MCP tools.
set -euo pipefail
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv run --with 'mcp<2' python3 - <<'EOF'
import asyncio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PATH = __PATH__

async def main():
    async with streamablehttp_client("http://game:8000/mcp") as streams:
        async with ClientSession(streams[0], streams[1]) as s:
            await s.initialize()
            for a in PATH:
                await s.call_tool("act", {"action": a})
            print(f"replayed {len(PATH)} actions")

asyncio.run(main())
EOF
"""

MAIN_DOCKERFILE = """FROM ubuntu:24.04
RUN apt-get update && apt-get install -y curl python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
"""

GAME_DOCKERFILE = """FROM python:3.12-slim
RUN pip install --no-cache-dir "mcp>=1.6,<2"
WORKDIR /srv
COPY engine /srv/engine
COPY arena /srv/arena
COPY contracts /srv/contracts
COPY collection.json /srv/collection.json
ENV PYTHONPATH=/srv ARENA_REPO_ROOT=/srv GAME_COLLECTION=/srv/collection.json PORT=8000
EXPOSE 8000
CMD ["python", "-m", "arena.harbor.sidecar"]
"""

COMPOSE = """# Merged on top of Harbor's base compose config; `main` is configured by Harbor.
services:
  main:
    depends_on:
      game:
        condition: service_healthy
  game:
    build:
      context: ./game
    environment:
      GAME_ID: "__GAME_ID__"
      SCORE_TOKEN: "__TOKEN__"
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"]
      interval: 2s
      timeout: 5s
      retries: 30
      start_period: 5s
"""


def _safe_name(game_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in game_id)


def export(collection: str, out: Path, first: int | None = None, agent_timeout: int = 3600, log=print) -> list[Path]:
    from ..engine_adapter import load_engine
    eng, name = load_engine()
    if name != "engine":
        raise SystemExit("harbor export needs A1's engine package (pip install -e ./engine)")
    root = _repo_root()
    coll_file = Path(collection) if Path(collection).exists() else root / "data" / "collections" / f"{collection}.json"
    coll = json.loads(coll_file.read_text())
    games = coll["games"][: first or None]
    arena_src = Path(__file__).resolve().parents[1]
    engine_src = root / "engine" / "src" / "engine"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for g in games:
        gid = g["game_id"]
        game = eng.load_game(coll_file, gid)
        path = [a for lv in game.describe()["levels"] for a in lv["optimal_path"]]
        token = secrets.token_hex(16)
        t = out / _safe_name(gid)
        if t.exists():
            shutil.rmtree(t)
        (t / "environment" / "game").mkdir(parents=True)
        (t / "tests").mkdir()
        (t / "solution").mkdir()
        (t / "task.toml").write_text(_task_toml(_safe_name(gid), agent_timeout))
        (t / "instruction.md").write_text(INSTRUCTION)
        (t / "environment" / "Dockerfile").write_text(MAIN_DOCKERFILE)
        (t / "environment" / "docker-compose.yaml").write_text(COMPOSE.replace("__GAME_ID__", gid)
                                                               .replace("__TOKEN__", token))
        gd = t / "environment" / "game"
        (gd / "Dockerfile").write_text(GAME_DOCKERFILE)
        shutil.copytree(engine_src, gd / "engine", ignore=shutil.ignore_patterns("__pycache__", "tests"))
        for f in SIDECAR_FILES:
            dst = gd / "arena" / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arena_src / f, dst)
        (gd / "contracts").mkdir()
        shutil.copy2(root / "contracts" / "palette.json", gd / "contracts" / "palette.json")
        (gd / "collection.json").write_text(json.dumps({**{k: v for k, v in coll.items() if k != "games"},
                                                        "games": [g]}))
        (t / "tests" / "test.sh").write_text(TEST_SH.replace("__TOKEN__", token), newline="\n")
        (t / "solution" / "solve.sh").write_text(SOLVE_SH.replace("__PATH__", json.dumps(path)), newline="\n")
        made.append(t)
    log(f"exported {len(made)} Harbor tasks from {coll_file.name} -> {out}")
    return made
