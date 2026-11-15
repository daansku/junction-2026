"""End-to-end smoke test against a running server.

    python scripts/smoke.py [--api http://localhost:8000]   (default: $API_URL, else localhost:8000)

Creates a session, plays the first game to a win with the optimal path, ends it, and finds the run via /runs.
Exit code 0 on success.
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--local", action="store_true", help="start a throwaway server on :8765 with a temp DATA_DIR")
    ap.add_argument("--collection", default="dev")
    args = ap.parse_args()
    if args.local:
        return _with_local_server(args)
    return _smoke(args)


def _with_local_server(args) -> int:
    import subprocess
    import tempfile
    import time

    tmp = tempfile.mkdtemp(prefix="smoke-")
    log = open(os.path.join(tmp, "server.log"), "w")
    env = dict(os.environ, DATA_DIR=tmp, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen([sys.executable, "-m", "server", "serve", "--host", "127.0.0.1", "--port", "8765"],
                            stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        for _ in range(100):
            try:
                httpx.get("http://127.0.0.1:8765/api/health", timeout=1).raise_for_status()
                break
            except Exception:  # noqa: BLE001
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
        args.api = "http://127.0.0.1:8765"
        try:
            return _smoke(args)
        except BaseException as e:  # noqa: BLE001
            log.flush()
            print(open(log.name).read()[-3000:])
            print(f"FAIL {type(e).__name__}: {e}")
            return int(getattr(e, "code", 1) or 1)
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def _smoke(args) -> int:
    base = args.api.rstrip("/")
    base = base if base.endswith("/api") else base + "/api"
    c = httpx.Client(base_url=base, timeout=30)

    def ok(cond: bool, msg: str) -> None:
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            sys.exit(1)

    h = c.get("/health").json()
    ok(h.get("ok") is True, f"health: engine={h.get('engine')} {h.get('engine_version')}")
    games = c.get("/games", params={"collection": args.collection}).json()
    ok(len(games) > 0, f"catalogue: {len(games)} games in {args.collection}")
    gid = games[0]["game_id"]
    desc = c.get(f"/games/{gid}", params={"collection": args.collection}).json()
    s = c.post("/sessions", json={"game_id": gid, "collection": args.collection,
                                  "player": {"kind": "baseline", "name": "smoke-optimal"}}).json()
    ok(len(s["frame"]) == 64, f"session {s['session_id'][:8]} run {s['run_id']}")
    n = 0
    for lv in desc["levels"]:
        for a in lv["optimal_path"]:
            r = c.post(f"/sessions/{s['session_id']}/act", json={"action": a})
            r.raise_for_status()
            ok_keys = set(r.json()) == {"frame", "available_actions"}
            if not ok_keys:
                ok(False, f"act response leaks fields: {sorted(r.json())}")
            n += 1
    t = c.get(f"/sessions/{s['session_id']}/truth").json()
    ok(t["state"] == "WIN", f"won {desc['levels_total']} levels in {n} actions")
    meta = c.post(f"/sessions/{s['session_id']}/end", json={"reason": "smoke"}).json()
    ok(meta["outcome"] == "WIN", "run closed with outcome WIN")
    runs = c.get("/runs", params={"game_id": gid, "kind": "baseline"}).json()
    ok(any(r["run_id"] == s["run_id"] for r in runs), "run found via /runs")
    steps = c.get(f"/runs/{s['run_id']}/steps").json()
    ok(len(steps) == n + 1, f"replay has {len(steps)} steps")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
