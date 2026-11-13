"""MCP server exposing one Switchboard episode to an agent (Harbor + OpenCode connect here).

    SWITCHBOARD_SEED=3 SWITCHBOARD_TIER=hard python -m switchboard.mcp_server            # stdio
    python -m switchboard.mcp_server --transport streamable-http --port 8765             # HTTP

The score is computed only from simulator state held in this process and written to
SWITCHBOARD_RESULT (default results/mcp_episode.json) after every action, so a verifier
can read it even if the agent quits or crashes. Nothing the agent says can change it.
The wiring/seed never leave this process; run it outside the agent's sandbox.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .env import SwitchboardEnv

SEED = int(os.environ.get("SWITCHBOARD_SEED", "0"))
TIER = os.environ.get("SWITCHBOARD_TIER", "hard")
RESULT = Path(os.environ.get("SWITCHBOARD_RESULT", "results/mcp_episode.json"))

env = SwitchboardEnv(SEED, TIER)
mcp = FastMCP("switchboard", instructions=env.instructions())


def _record(out: dict) -> dict:
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps({"summary": env.summary(), "history": env.history}, indent=1))
    return out


@mcp.tool()
def get_rules() -> str:
    """Free. The full rulebook: goal, budget, scoring and every possible kind of switch rule."""
    return env.instructions()


@mcp.tool()
def get_state() -> dict:
    """Free. Current lamps, current target, budget and progress."""
    return env.observe()


@mcp.tool()
def press(switch: str) -> dict:
    """Press one switch (a letter like 'A'). Costs 1 budget. Returns the new state."""
    return _record(env.press(switch))


@mcp.tool()
def reset() -> dict:
    """Restore the starting lamps and clear hidden press counts/unlocks. Costs the reset cost.
    Completed targets stay completed."""
    return _record(env.reset())


@mcp.tool()
def finish() -> dict:
    """End the episode now. Only do this if you cannot make further progress."""
    return _record(env.finish())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http", "sse"])
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    _record({})
    if args.transport != "stdio":
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
