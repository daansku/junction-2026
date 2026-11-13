"""python -m server [serve|mcp] ...

  python -m server                         serve REST + WS on 0.0.0.0:8000
  python -m server serve --port 8000 --reload
  python -m server mcp                     MCP over stdio (local sessions, recorded to DATA_DIR)
  python -m server mcp --api URL           MCP over stdio, proxying to a running server (e.g. the shared one)
"""
from __future__ import annotations

import argparse
import logging
import os


def main() -> None:
    ap = argparse.ArgumentParser(prog="server")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve")
    s.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    s.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    s.add_argument("--reload", action="store_true")
    m = sub.add_parser("mcp")
    m.add_argument("--api", default=None, help="proxy to this server URL instead of running games in-process")
    m.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http", "sse"])
    m.add_argument("--port", type=int, default=8001)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "mcp":
        from .mcp_server import run_mcp
        run_mcp(api=args.api, transport=args.transport, port=args.port)
        return
    import uvicorn
    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 8000)
    uvicorn.run("server.app:app", host=host, port=port, reload=getattr(args, "reload", False))


if __name__ == "__main__":
    main()
