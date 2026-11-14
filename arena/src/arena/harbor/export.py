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
  environment/game/         sidecar image: engine + arena sidecar + one-game collection
  tests/test.sh             separate verifier: reads the collected /evidence/score.json -> /logs/verifier/reward.*
  solution/solve.sh         oracle: replays the optimal path through MCP
"""
from __future__ import annotations

import json
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
# Separate container: the agent never shares a filesystem or network namespace with grading.
environment_mode = "separate"

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

# The game sidecar writes its score here after every action; Harbor collects it after the agent phase
# (agent container already stopped) and places it at the same path in the separate verifier.
[[artifacts]]
source = "/evidence/score.json"
service = "game"
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
# Separate verifier: read the score the game sidecar wrote (collected by Harbor as an artifact).
set -u
mkdir -p /logs/verifier
python3 - <<'EOF'
import json
try:
    s = json.load(open("/evidence/score.json"))
except Exception as e:  # missing evidence = no credit
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
# Stop-early baseline: same script with ORACLE_STOP_AFTER_LEVELS=<n> (harbor run -a oracle
# --ae ORACLE_STOP_AFTER_LEVELS=1) plays only the first n levels optimally, then stops.
# Standard-library MCP client only: no downloads, so it works offline and behind TLS-inspecting proxies.
set -euo pipefail
python3 - <<'EOF'
__MINI__

import os

LEVELS = __LEVELS__
STOP = int(os.environ.get("ORACLE_STOP_AFTER_LEVELS") or len(LEVELS))
PATH_ = [a for lv in LEVELS[:STOP] for a in lv]
c = MiniMCP("http://game:8000/mcp")
c.initialize()
for a in PATH_:
    c.call("act", {"action": a})
print(f"replayed {len(PATH_)} actions over {min(STOP, len(LEVELS))}/{len(LEVELS)} levels")
EOF
"""

MAIN_DOCKERFILE = """FROM ubuntu:24.04
RUN apt-get update && apt-get install -y curl python3 ca-certificates && rm -rf /var/lib/apt/lists/*
__EXTRA_CA__WORKDIR /app
"""

# Local-only: trust an extra root CA (e.g. antivirus TLS scanning) inside task containers.
# Never used for tasks we hand to judges; `--extra-ca` must be passed explicitly.
EXTRA_CA_MAIN = """COPY extra-ca.crt /usr/local/share/ca-certificates/extra-ca.crt
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt UV_NATIVE_TLS=1
"""

GAME_DOCKERFILE = """FROM python:3.12-slim
__EXTRA_CA____PIP_INSTALL__
WORKDIR /srv
COPY engine /srv/engine
COPY arena /srv/arena
COPY contracts /srv/contracts
COPY collection.json /srv/collection.json
ENV PYTHONPATH=/srv:/srv/vendor ARENA_REPO_ROOT=/srv GAME_COLLECTION=/srv/collection.json PORT=8000
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


PIP_ONLINE = 'RUN pip install --no-cache-dir "mcp>=1.6,<2"\n'
# Local-only: Linux site-packages prepared on the host with
#   uv pip install --target <dir> --python-platform x86_64-manylinux_2_17 --python-version 3.12 "mcp>=1.6,<2"
# and copied in, so the build needs no network (TLS-inspecting antivirus breaks pip downloads).
PIP_VENDOR = 'COPY vendor /srv/vendor\n'


def export(collection: str, out: Path, first: int | None = None, agent_timeout: int = 3600, log=print,
           extra_ca: Path | None = None, vendor: Path | None = None) -> list[Path]:
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
        levels = [list(lv["optimal_path"]) for lv in game.describe()["levels"]]
        path = [a for lv in levels for a in lv]
        t = out / _safe_name(gid)
        if t.exists():
            shutil.rmtree(t)
        (t / "environment" / "game").mkdir(parents=True)
        (t / "tests").mkdir()
        (t / "solution").mkdir()
        (t / "task.toml").write_text(_task_toml(_safe_name(gid), agent_timeout))
        (t / "instruction.md").write_text(INSTRUCTION)
        ca_block = EXTRA_CA_MAIN if extra_ca else ""
        (t / "environment" / "Dockerfile").write_text(MAIN_DOCKERFILE.replace("__EXTRA_CA__", ca_block), newline="\n")
        (t / "environment" / "docker-compose.yaml").write_text(COMPOSE.replace("__GAME_ID__", gid))
        gd = t / "environment" / "game"
        pip_block = PIP_VENDOR if vendor else PIP_ONLINE
        (gd / "Dockerfile").write_text(GAME_DOCKERFILE.replace("__EXTRA_CA__", ca_block)
                                       .replace("__PIP_INSTALL__\n", pip_block), newline="\n")
        if vendor:
            shutil.copytree(vendor, gd / "vendor", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if extra_ca:
            shutil.copy2(extra_ca, t / "environment" / "extra-ca.crt")
            shutil.copy2(extra_ca, gd / "extra-ca.crt")
        shutil.copytree(engine_src, gd / "engine", ignore=shutil.ignore_patterns("__pycache__", "tests"))
        for f in SIDECAR_FILES:
            dst = gd / "arena" / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arena_src / f, dst)
        (gd / "contracts").mkdir()
        shutil.copy2(root / "contracts" / "palette.json", gd / "contracts" / "palette.json")
        (gd / "collection.json").write_text(json.dumps({**{k: v for k, v in coll.items() if k != "games"},
                                                        "games": [g]}))
        (t / "tests" / "test.sh").write_text(TEST_SH, newline="\n")
        mini = (Path(__file__).parent / "mcp_mini.py").read_text(encoding="utf-8")
        solve = SOLVE_SH.replace("__MINI__", mini).replace("__LEVELS__", json.dumps(levels))
        (t / "solution" / "solve.sh").write_text(solve, newline="\n")
        made.append(t)
    log(f"exported {len(made)} Harbor tasks from {coll_file.name} -> {out}"
        + (f" (LOCAL ONLY: extra CA {extra_ca.name} baked in; do not hand these to judges)" if extra_ca else ""))
    return made
