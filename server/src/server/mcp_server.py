"""MCP server: tools list_games, start_game, act, reset. Pixels only.

Every tool that shows the game returns the frame as a PNG image AND as a text grid
(64 lines of 64 hex chars, palette index per cell). No state, score, budget numbers or rule names.

Backends:
  in-process (default): runs games with the local SessionManager; traces go to DATA_DIR.
  --api URL: proxies to a running server (the shared one), so traces land centrally.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP, Image

from .render import frame_to_png, frame_to_text

INSTRUCTIONS = (
    "You are playing a grid game shown as a 64x64 image. Each tool returns the current frame as an image and as a "
    "text grid (one hex digit 0-f per cell = colour index). Actions: ACTION1=up, ACTION2=down, ACTION3=left, "
    "ACTION4=right, ACTION5=interact, RESET=restart the current level. Work out the goal and the rules by acting. "
    "Call list_games, then start_game, then act repeatedly."
)


class _LocalBackend:
    def __init__(self) -> None:
        from . import engine_adapter
        from .recorder import Recorder
        from .sessions import SessionManager
        self.engine_adapter = engine_adapter
        self.sessions = SessionManager(Recorder())

    def list_games(self, collection: str) -> list[dict]:
        return self.engine_adapter.list_games(collection)

    def start(self, game_id: str, player: dict, collection: Optional[str]) -> dict:
        return self.sessions.start(game_id, player, collection)

    def act(self, sid: str, action: str, x, y, note) -> dict:
        return self.sessions.act(sid, action, x, y, reasoning=note)

    def end(self, sid: str, reason: str) -> None:
        self.sessions.end(sid, reason)


class _HttpBackend:
    def __init__(self, base: str) -> None:
        import httpx
        base = base.rstrip("/")
        self.base = base if base.endswith("/api") else base + "/api"
        self.c = httpx.Client(timeout=60)

    def _req(self, method: str, path: str, **kw) -> Any:
        r = self.c.request(method, self.base + path, **kw)
        r.raise_for_status()
        return r.json()

    def list_games(self, collection: str) -> list[dict]:
        return self._req("GET", "/games", params={"collection": collection})

    def start(self, game_id: str, player: dict, collection: Optional[str]) -> dict:
        return self._req("POST", "/sessions", json={"game_id": game_id, "player": player, "collection": collection})

    def act(self, sid: str, action: str, x, y, note) -> dict:
        body = {"action": action, "x": x, "y": y, "reasoning": note}
        return self._req("POST", f"/sessions/{sid}/act", json={k: v for k, v in body.items() if v is not None})

    def end(self, sid: str, reason: str) -> None:
        self._req("POST", f"/sessions/{sid}/end", json={"reason": reason})


def build_mcp(api: Optional[str] = None, player: Optional[dict] = None, collection: str = "dev",
              port: int = 8001) -> FastMCP:
    backend = _HttpBackend(api) if api else _LocalBackend()
    player = player or {
        "kind": "model",
        "name": os.environ.get("MCP_PLAYER_NAME", "mcp-agent"),
        "model_id": os.environ.get("MCP_MODEL_ID"),
        "provider": os.environ.get("MCP_PROVIDER"),
    }
    state: dict[str, Any] = {"sid": None, "game_id": None}
    mcp = FastMCP("junction-grid-games", instructions=INSTRUCTIONS, host="0.0.0.0", port=port)

    def _show(resp: dict) -> list:
        frame = resp["frame"]
        actions = ", ".join(resp.get("available_actions", []))
        return [Image(data=frame_to_png(frame, scale=8), format="png"),
                f"Available actions: {actions}\nFrame (64 rows x 64 hex cells):\n{frame_to_text(frame)}"]

    @mcp.tool()
    def list_games() -> list[str]:
        """List the game ids you can play."""
        return [g["game_id"] for g in backend.list_games(collection)]

    @mcp.tool()
    def start_game(game_id: str) -> list:
        """Start (or restart from level 1) the game with this id. Returns the first frame."""
        if state["sid"]:
            try:
                backend.end(state["sid"], "restarted")
            except Exception:  # noqa: BLE001
                pass
        resp = backend.start(game_id, player, collection)
        state.update(sid=resp["session_id"], game_id=game_id)
        return _show(resp)

    @mcp.tool()
    def act(action: str, x: Optional[int] = None, y: Optional[int] = None, note: Optional[str] = None) -> list:
        """Take one action: ACTION1 (up), ACTION2 (down), ACTION3 (left), ACTION4 (right), ACTION5 (interact),
        RESET (restart the current level). `note` is your optional reasoning, saved with the replay."""
        if not state["sid"]:
            return ["No game running. Call start_game first."]
        try:
            return _show(backend.act(state["sid"], action, x, y, note))
        except Exception as e:  # noqa: BLE001 - invalid action etc.; report without leaking internals
            detail = getattr(e, "detail", None) or "action rejected"
            return [f"Error: {detail}"]

    @mcp.tool()
    def reset() -> list:
        """Restart the current level (same as act RESET)."""
        return act("RESET")

    return mcp


def run_mcp(api: Optional[str] = None, transport: str = "stdio", port: int = 8001) -> None:
    build_mcp(api, port=port).run(transport=transport)
