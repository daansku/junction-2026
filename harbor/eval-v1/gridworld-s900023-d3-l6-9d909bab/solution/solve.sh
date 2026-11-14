#!/bin/bash
# Oracle (reference run): replay the engine's optimal path through the game's MCP tools.
# Stop-early baseline: same script with ORACLE_STOP_AFTER_LEVELS=<n> (harbor run -a oracle
# --ae ORACLE_STOP_AFTER_LEVELS=1) plays only the first n levels optimally, then stops.
# Standard-library MCP client only: no downloads, so it works offline and behind TLS-inspecting proxies.
set -euo pipefail
python3 - <<'EOF'
"""Minimal MCP streamable-HTTP client using only the Python standard library.

Used by the oracle's solve.sh so the reference run needs no downloads (no uv, no pip) inside the
agent container. Supports exactly what the oracle needs: initialize, notifications/initialized,
tools/call. Responses may be plain JSON or a server-sent-event stream.
"""
from __future__ import annotations

import http.client
import json
import urllib.request

PROTOCOL = "2025-03-26"


class MiniMCP:
    def __init__(self, url: str, timeout: float = 60):
        self.url, self.timeout = url, timeout
        self.session: str | None = None
        self._id = 0

    def _post(self, payload: dict) -> dict | None:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["mcp-session-id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            self.session = r.headers.get("mcp-session-id") or self.session
            if "id" not in payload:  # notification: 202 with an (often empty, chunked) body we don't need
                return None
            ctype = r.headers.get("content-type", "")
            try:
                body = r.read().decode()
            except http.client.IncompleteRead as e:  # SSE stream closed without a final chunk
                body = e.partial.decode()
        if not body.strip():
            return None
        if "text/event-stream" in ctype:
            for line in body.splitlines():
                if line.startswith("data:"):
                    msg = json.loads(line[5:].strip())
                    if msg.get("id") == payload["id"]:
                        return msg
            raise RuntimeError("no response event for request")
        return json.loads(body)

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        if msg is None or "error" in msg:
            raise RuntimeError(f"{method} failed: {msg}")
        return msg["result"]

    def initialize(self) -> dict:
        res = self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                          "clientInfo": {"name": "arena-oracle", "version": "1"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return res

    def call(self, tool: str, args: dict) -> dict:
        return self.request("tools/call", {"name": tool, "arguments": args})


import os

LEVELS = [["ACTION3", "ACTION1", "ACTION1", "ACTION1", "ACTION1", "ACTION3", "ACTION3", "ACTION1", "ACTION1", "ACTION1", "ACTION1", "ACTION1", "ACTION3", "ACTION3", "ACTION2", "ACTION3", "ACTION2", "ACTION3", "ACTION2", "ACTION2", "ACTION2", "ACTION3"], ["ACTION1", "ACTION1", "ACTION3", "ACTION1", "ACTION1", "ACTION4", "ACTION4", "ACTION4", "ACTION4", "ACTION4", "ACTION2", "ACTION2", "ACTION2", "ACTION4"], ["ACTION3", "ACTION2", "ACTION3", "ACTION3", "ACTION3", "ACTION3", "ACTION1", "ACTION1", "ACTION1", "ACTION1", "ACTION1", "ACTION1", "ACTION3"], ["ACTION1", "ACTION3", "ACTION2", "ACTION4", "ACTION1", "ACTION4", "ACTION4", "ACTION2", "ACTION2", "ACTION2", "ACTION3", "ACTION2", "ACTION2", "ACTION2", "ACTION4", "ACTION4"], ["ACTION4", "ACTION1", "ACTION2", "ACTION2", "ACTION2", "ACTION3", "ACTION2", "ACTION2", "ACTION4", "ACTION4", "ACTION4"], ["ACTION1", "ACTION1", "ACTION1", "ACTION4", "ACTION4", "ACTION4", "ACTION2", "ACTION2", "ACTION2", "ACTION2", "ACTION3", "ACTION3", "ACTION1", "ACTION3", "ACTION3", "ACTION3", "ACTION1", "ACTION1", "ACTION4", "ACTION1", "ACTION1", "ACTION1", "ACTION1", "ACTION1"]]
STOP = int(os.environ.get("ORACLE_STOP_AFTER_LEVELS") or len(LEVELS))
PATH_ = [a for lv in LEVELS[:STOP] for a in lv]
c = MiniMCP("http://game:8000/mcp")
c.initialize()
for a in PATH_:
    c.call("act", {"action": a})
print(f"replayed {len(PATH_)} actions over {min(STOP, len(LEVELS))}/{len(LEVELS)} levels")
EOF
