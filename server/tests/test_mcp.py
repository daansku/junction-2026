"""Plays a level through the real MCP stdio server with the official MCP client."""
import asyncio
import os
import sys

import pytest

mcp = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


async def _play(tmp_path):
    params = StdioServerParameters(command=sys.executable, args=["-m", "server", "mcp"],
                                   env={**os.environ, "DATA_DIR": str(tmp_path)})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            assert tools == {"list_games", "start_game", "act", "reset"}
            res = await s.call_tool("list_games", {})
            ids = [c.text for c in res.content if c.type == "text"]
            game_id = ids[0].strip('[]" ').split('"')[0] if ids[0].startswith("[") else ids[0]
            res = await s.call_tool("start_game", {"game_id": game_id})
            kinds = [c.type for c in res.content]
            assert kinds == ["image", "text"]
            text = res.content[1].text
            rows = [l for l in text.splitlines() if len(l) == 64 and all(ch in "0123456789abcdef" for ch in l)]
            assert len(rows) == 64
            # pixels only: no hidden state leaks
            for word in ("WIN", "GAME_OVER", "budget", "optimal", "rule", "level"):
                assert word.lower() not in text.lower().replace("available actions", "")
            res = await s.call_tool("act", {"action": "ACTION1", "note": "testing"})
            assert [c.type for c in res.content] == ["image", "text"]
            res = await s.call_tool("act", {"action": "JUMP"})
            assert "Error" in res.content[0].text
            res = await s.call_tool("reset", {})
            assert res.content[0].type == "image"


def test_mcp_stdio(tmp_path):
    asyncio.run(asyncio.wait_for(_play(tmp_path), 60))
    runs = list((tmp_path / "runs").glob("*/steps.jsonl"))
    assert len(runs) == 1
    assert len(runs[0].read_text().splitlines()) == 3  # initial frame, ACTION1, RESET (invalid JUMP not recorded)
