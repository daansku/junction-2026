"""Game clients. HttpClient talks to A2's server (PLAN.md §4.4); MockClient runs MockGame in-process.

The harness only ever shows the model `frame` + `available_actions`. `truth()` is used by
the runner to know when a game ended; it is never put in a prompt.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Protocol

from .mock_game import ACTIONS, MockGame


class Session(Protocol):
    session_id: str
    run_id: str

    def act(self, action: str, **extra) -> dict: ...
    def truth(self) -> dict: ...
    def end(self, reason: str) -> None: ...


class GameClient(Protocol):
    def list_games(self, collection: str) -> list[dict]: ...
    def describe(self, game_id: str) -> dict: ...
    def start(self, game_id: str, player: dict, run_key: str | None = None) -> tuple[Session, dict]: ...
    def finished_run_keys(self) -> set[str]: ...


# ---------------------------------------------------------------- HTTP
class HttpSession:
    def __init__(self, http, data: dict):
        self.http = http
        self.session_id = data["session_id"]
        self.run_id = data.get("run_id", "")

    def act(self, action: str, **extra) -> dict:
        body = {"action": action, **{k: v for k, v in extra.items() if v is not None}}
        return self.http.post(f"/sessions/{self.session_id}/act", body)

    def truth(self) -> dict:
        return self.http.get(f"/sessions/{self.session_id}/truth")

    def end(self, reason: str, outcome: str | None = None, usage_total: dict | None = None) -> None:
        body = {"reason": reason, "outcome": outcome, "usage_total": usage_total}
        self.http.post(f"/sessions/{self.session_id}/end", {k: v for k, v in body.items() if v is not None})


class AlreadyFinished(Exception):
    """POST /sessions returned 409: this run_key already has a finished run."""


class _Http:
    def __init__(self, base: str, transport=None, backoff: float = 1.5):
        import httpx
        self.base = base.rstrip("/")
        if not self.base.endswith("/api"):
            self.base += "/api"
        self.backoff = backoff
        self.c = httpx.Client(timeout=60, transport=transport)

    def _do(self, method, path, **kw):
        import httpx
        for attempt in range(4):
            try:
                r = self.c.request(method, self.base + path, **kw)
            except httpx.TransportError:  # network blips on a venue tunnel
                if attempt == 3:
                    raise
                time.sleep(self.backoff * 2 ** attempt)
                continue
            if r.status_code >= 500 and attempt < 3:
                time.sleep(self.backoff * 2 ** attempt)
                continue
            if r.status_code == 409 and method == "POST" and path == "/sessions":
                raise AlreadyFinished(r.text)
            r.raise_for_status()  # 4xx are our bugs: fail loudly, no retry
            return r.json() if r.content else {}

    def get(self, path, **params):
        return self._do("GET", path, params=params)

    def post(self, path, body):
        return self._do("POST", path, json=body)


class HttpClient:
    def __init__(self, base_url: str, collection: str | None = None, transport=None, backoff: float = 1.5):
        self.http = _Http(base_url, transport=transport, backoff=backoff)
        self.collection = collection

    def list_games(self, collection: str) -> list[dict]:
        self.collection = collection
        out = self.http.get("/games", collection=collection)
        return out if isinstance(out, list) else out.get("games", [])

    def describe(self, game_id: str) -> dict:
        return self.http.get(f"/games/{game_id}")

    def start(self, game_id, player, run_key=None):
        body = {"game_id": game_id, "collection": self.collection, "run_key": run_key,
                "harness_version": player.get("harness_version"),
                "player": player}
        data = self.http.post("/sessions", {k: v for k, v in body.items() if v is not None})
        return HttpSession(self.http, data), data

    def finished_run_keys(self) -> set[str]:
        params = {"limit": 100000}
        if self.collection:
            params["collection"] = self.collection
        runs = self.http.get("/runs", **params)
        runs = runs if isinstance(runs, list) else runs.get("runs", [])
        return {r["run_key"] for r in runs
                if r.get("run_key") and r.get("ended_at") and r.get("outcome") != "IN_PROGRESS"}

    def running_run_keys(self, max_age_s: float = 4 * 3600) -> set[str]:
        """Keys with a run IN_PROGRESS that started within max_age_s (another runner is playing them now)."""
        import datetime as _dt
        params = {"limit": 100000}
        if self.collection:
            params["collection"] = self.collection
        runs = self.http.get("/runs", **params)
        runs = runs if isinstance(runs, list) else runs.get("runs", [])
        now = _dt.datetime.now(_dt.timezone.utc)
        out = set()
        for r in runs:
            if r.get("run_key") and r.get("outcome") == "IN_PROGRESS" and r.get("started_at"):
                try:
                    t = _dt.datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
                except ValueError:
                    continue
                if (now - t).total_seconds() < max_age_s:
                    out.add(r["run_key"])
        return out

    def infra_aborted_run_keys(self) -> set[str]:
        """Finished keys the server ended itself (idle_timeout or server_restart: runner, tunnel or server died)."""
        params = {"limit": 100000}
        if self.collection:
            params["collection"] = self.collection
        runs = self.http.get("/runs", **params)
        runs = runs if isinstance(runs, list) else runs.get("runs", [])
        infra = lambda r: r.get("outcome") == "ABORTED" and r.get("end_reason") in ("idle_timeout", "server_restart")
        real = {r["run_key"] for r in runs if r.get("run_key") and r.get("ended_at")
                and r.get("outcome") != "IN_PROGRESS" and not infra(r)}
        return {r["run_key"] for r in runs if r.get("run_key") and infra(r)} - real  # a real result wins


# ---------------------------------------------------------------- mock
class MockSession:
    def __init__(self, client: "MockClient", game: MockGame, player: dict, run_key):
        self.client, self.game = client, game
        self.session_id = uuid.uuid4().hex[:12]
        self.run_id = self.session_id
        self.meta = {"run_id": self.run_id, "run_key": run_key, "game_id": game.game_id, "player": player,
                     "started_at": time.time(), "ended_at": None}
        self.steps: list[dict] = []

    def act(self, action: str, **extra) -> dict:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action}")
        frame = self.game.step(action)
        self.steps.append({"i": len(self.steps), "action": action, "truth": self.game.truth(), **extra})
        return {"frame": frame, "available_actions": ACTIONS}

    def truth(self) -> dict:
        return self.game.truth()

    def end(self, reason: str, outcome: str | None = None, usage_total: dict | None = None) -> None:
        t = self.game.truth()
        self.meta.update(ended_at=time.time(), reason=reason, outcome=t["state"],
                         levels_completed=t["level"] - (0 if t["state"] == "WIN" else 1),
                         levels_total=t["levels_total"], actions=len(self.steps))
        self.client.record(self)


class MockClient:
    """In-process games named mock-s<seed>-l<levels>. Ledger file makes resume testable."""

    def __init__(self, ledger: str | os.PathLike | None = None):
        self.ledger = Path(ledger) if ledger else None
        self.sessions: list[MockSession] = []
        self._lock = threading.Lock()

    @staticmethod
    def _game(game_id: str) -> MockGame:
        # mock-s<seed>-l<levels>
        _, s, l = game_id.split("-")
        return MockGame(int(s[1:]), int(l[1:]))

    def list_games(self, collection: str) -> list[dict]:
        return [{"game_id": f"mock-s{i}-l3"} for i in range(5)]

    def describe(self, game_id: str) -> dict:
        return self._game(game_id).describe()

    def start(self, game_id, player, run_key=None):
        g = self._game(game_id)
        s = MockSession(self, g, player, run_key)
        self.sessions.append(s)
        return s, {"session_id": s.session_id, "run_id": s.run_id, "frame": g.reset(), "available_actions": ACTIONS}

    def record(self, s: MockSession) -> None:
        if self.ledger:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps({k: v for k, v in s.meta.items() if k != "player"}) + "\n"
            with self._lock, self.ledger.open("a") as f:
                f.write(line)

    def finished_run_keys(self) -> set[str]:
        keys = {s.meta["run_key"] for s in self.sessions if s.meta["ended_at"]}
        if self.ledger and self.ledger.exists():
            keys |= {json.loads(l)["run_key"] for l in self.ledger.read_text().splitlines() if l.strip()}
        return {k for k in keys if k}


def make_client(api: str, ledger=None) -> GameClient:
    """api: 'mock' | 'local' | 'shared' | an explicit URL."""
    if api == "mock":
        return MockClient(ledger)
    if api == "local":
        return HttpClient(os.environ.get("ARENA_LOCAL_API", "http://localhost:8000"))
    if api == "shared":
        from .frames import _repo_root
        p = _repo_root() / "API_URL"
        if not p.exists():
            raise SystemExit("API_URL file not found at the repo root; use --api local, mock or a URL")
        return HttpClient(p.read_text().strip())
    return HttpClient(api)
