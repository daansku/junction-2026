"""Game sidecar for Harbor tasks: one fixed game, MCP over streamable HTTP, pixels only.

Runs in its own container next to the agent. The agent can reach it over the compose network, so the
surface is deliberately tiny:
  MCP tools   observe() - current frame (PNG + text grid), free
              act(action, note?) - one action; returns the new frame
  HTTP        GET /healthz
Nothing else: no game list, no restart-from-level-1, no truth, no optimal path, no score endpoint.
The score is written to EVIDENCE (default /evidence/score.json) inside this container after every
action. Harbor collects it as an artifact after the agent phase (agent container already stopped)
and hands it to a separate verifier container. The agent has no route to that file.

Score: mean over levels of min(1, optimal_moves / actions_on_level)
for solved levels, 0 otherwise. Every counted action (moves and RESETs) on a level counts against it.

    GAME_COLLECTION=/game/collection.json GAME_ID=... python -m arena.harbor.sidecar
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image
from starlette.requests import Request  # noqa: F401 (custom_route handler signature)
from starlette.responses import JSONResponse

INSTRUCTIONS = (
    "A video game you have never seen. Each tool returns the screen as a 64x64 image and as a text grid "
    "(one hex digit 0-f per cell = colour index, row 0 at the top). Actions: ACTION1=up, ACTION2=down, "
    "ACTION3=left, ACTION4=right, ACTION5=interact (only when listed as available), RESET=restart the current level. Nobody tells you the "
    "goal or the rules: find them by acting. Every action counts against your score."
)
MAX_ACTIONS = int(os.environ.get("MAX_ACTIONS", "3000"))
EVIDENCE = os.environ.get("EVIDENCE", "/evidence/score.json")


def png(frame: list[str], scale: int = 8) -> bytes:
    from arena.frames import to_png
    return to_png(frame, scale=scale)


class Episode:
    """Holds the game and the per-level action accounting. Thread-safe."""

    def __init__(self, game, optimal_by_level: list[int], evidence: str | None = None):
        self.evidence = Path(evidence) if evidence else None
        self.g = game
        self.optimal = optimal_by_level
        self.n = len(optimal_by_level)
        self.actions_on = [0] * self.n
        self.solved = [False] * self.n
        self.total = 0
        self.invalid = 0
        self.lock = threading.Lock()
        self.frame = game.frame() if hasattr(game, "frame") else game.reset()
        self.allowed = self._allowed()
        self._write()

    def _write(self) -> None:
        """Atomically persist the current score for the verifier (called under the lock or at init)."""
        if not self.evidence:
            return
        self.evidence.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.evidence.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._score()))
        os.replace(tmp, self.evidence)

    def _allowed(self) -> list[str]:
        return [getattr(a, "value", a) for a in self.g.available_actions()]

    def act(self, action: str) -> tuple[list[str], list[str], str | None]:
        with self.lock:
            a = str(action).strip().upper()
            t = self.g.truth()
            if t["state"] == "WIN":
                return self.frame, self.allowed, "the game is over"
            if self.total >= MAX_ACTIONS:
                return self.frame, self.allowed, "action limit reached"
            if a not in self.allowed:
                self.invalid += 1
                self._write()  # keep invalid_actions in score.json current (red team); reward unchanged
                return self.frame, self.allowed, f"invalid action; available: {', '.join(self.allowed)}"
            lvl = t["level"] - 1
            self.actions_on[lvl] += 1
            self.total += 1
            self.frame = self.g.step(a)
            t2 = self.g.truth()
            if t2["state"] == "WIN" or t2["level"] > t["level"]:
                self.solved[lvl] = True
            self.allowed = self._allowed()
            self._write()
            return self.frame, self.allowed, None

    def score(self) -> dict:
        with self.lock:
            return self._score()

    def _score(self) -> dict:
        per = [min(1.0, self.optimal[i] / self.actions_on[i]) if self.solved[i] and self.actions_on[i] else 0.0
               for i in range(self.n)]
        return {"reward": round(sum(per) / self.n, 6), "levels_solved": sum(self.solved),
                "levels_total": self.n, "actions": self.total, "invalid_actions": self.invalid,
                "per_level": [round(x, 4) for x in per], "won": self.g.truth()["state"] == "WIN"}


def load_episode(collection: str, game_id: str, evidence: str | None = None) -> Episode:
    from arena.engine_adapter import load_engine
    eng, _ = load_engine()
    g = eng.load_game(collection, game_id)
    desc = g.describe()
    return Episode(g, [lv["optimal_moves"] for lv in desc["levels"]], evidence)


def build(ep: Episode, port: int = 8000) -> FastMCP:
    mcp = FastMCP("game", instructions=INSTRUCTIONS, host="0.0.0.0", port=port)

    def show(frame, allowed, err=None) -> list:
        from arena.frames import to_text
        head = (f"Error: {err}\n" if err else "") + f"Available actions: {', '.join(allowed)}"
        return [Image(data=png(frame), format="png"), f"{head}\nScreen (64 rows x 64 hex cells):\n{to_text(frame)}"]

    @mcp.tool()
    def observe() -> list:
        """Show the current screen without acting (free)."""
        return show(ep.frame, ep.allowed)

    @mcp.tool()
    def act(action: str, note: str | None = None) -> list:
        """Take one action: ACTION1 (up), ACTION2 (down), ACTION3 (left), ACTION4 (right),
        ACTION5 (interact, only when listed as available), RESET (restart the current level). Returns the new screen."""
        return show(*ep.act(action))

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request: Request):
        return JSONResponse({"ok": True})

    return mcp


def main():
    ep = load_episode(os.environ["GAME_COLLECTION"], os.environ["GAME_ID"], EVIDENCE)
    build(ep, int(os.environ.get("PORT", "8000"))).run(transport="streamable-http")


if __name__ == "__main__":
    main()
