"""HttpClient against a fake server built from contracts/openapi.yaml + trace.schema.json.

The fake rejects request fields the contract doesn't define and validates every recorded step
and meta against the trace schema, so contract drift on either side fails here, not at 04:30.
"""
import datetime as dt
import json
import re
import uuid
from pathlib import Path

import httpx
import jsonschema
import pytest
import yaml

from arena.agent_loop import Budgets, play_model
from arena.baselines import BASELINES
from arena.client import AlreadyFinished, HttpClient, MockClient
from arena.mock_game import ACTIONS
from arena.providers.mock_provider import MockProvider
from arena.runner import execute

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text())
TRACE = json.loads((ROOT / "contracts" / "trace.schema.json").read_text())


def _schema(name):
    return {"$defs": TRACE["$defs"], **TRACE["$defs"][name]}


def _body_props(path):
    rb = OPENAPI["paths"][path]["post"].get("requestBody", {})
    return set(rb.get("content", {}).get("application/json", {}).get("schema", {}).get("properties", {}))


ALLOWED = {"start": _body_props("/sessions"), "act": _body_props("/sessions/{session_id}/act"),
           "end": _body_props("/sessions/{session_id}/end")}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class FakeServer:
    def __init__(self):
        self.games = MockClient()
        self.sessions = {}
        self.runs = {}
        self.t0 = {}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        p = req.url.path.removeprefix("/api")
        body = json.loads(req.content) if req.content else {}
        if req.method == "GET" and p == "/games":
            return httpx.Response(200, json=[{**g, "levels_total": 3, "thumbnail_url": ""}
                                             for g in self.games.list_games("dev")])
        if req.method == "GET" and p.startswith("/games/"):
            return httpx.Response(200, json=self.games.describe(p.split("/")[2]))
        if req.method == "POST" and p == "/sessions":
            extra = set(body) - ALLOWED["start"]
            assert not extra, f"start: fields not in contract {extra}"
            jsonschema.validate(body["player"], _schema("player"))
            rk = body.get("run_key")
            if rk and any(m["run_key"] == rk and m["ended_at"] for m in self.runs.values()):
                return httpx.Response(409, text="finished")
            s, start = self.games.start(body["game_id"], body["player"], run_key=rk)
            self.sessions[s.session_id] = s
            self.t0[s.session_id] = dt.datetime.now(dt.timezone.utc)
            self.runs[s.run_id] = {"run_id": s.run_id, "run_key": rk, "game_id": body["game_id"],
                                   "collection": body.get("collection"), "player": body["player"],
                                   "harness_version": body.get("harness_version"), "started_at": now(),
                                   "ended_at": None, "outcome": "IN_PROGRESS", "levels_completed": 0,
                                   "levels_total": 3, "actions": 0, "resets": 0, "steps": []}
            return httpx.Response(200, json={"session_id": s.session_id, "run_id": s.run_id,
                                             "frame": start["frame"], "available_actions": ACTIONS})
        m = re.fullmatch(r"/sessions/([^/]+)/(act|truth|end)", p)
        if m:
            s = self.sessions[m.group(1)]
            run = self.runs[s.run_id]
            if m.group(2) == "truth":
                return httpx.Response(200, json=s.truth())
            if m.group(2) == "act":
                extra = set(body) - ALLOWED["act"]
                assert not extra, f"act: fields not in contract {extra}"
                if body["action"] not in ACTIONS:
                    return httpx.Response(422)
                out = s.act(body["action"])
                step = {"i": len(run["steps"]) + 1, "t_ms": 1, "action": body["action"], "frame": out["frame"],
                        "truth": s.truth(), **{k: body.get(k) for k in ("reasoning", "hypothesis", "belief",
                                                                      "latency_ms")}}
                if body.get("usage") is not None:
                    step["usage"] = body["usage"]
                jsonschema.validate(step, _schema("step"))
                run["steps"].append(step)
                run["actions"] += 1
                return httpx.Response(200, json=out)
            extra = set(body) - ALLOWED["end"]
            assert not extra, f"end: fields not in contract {extra}"
            t = s.truth()
            run.update(ended_at=now(), outcome=body.get("outcome") or "ABORTED", end_reason=body.get("reason"),
                       levels_completed=t["level"] - (0 if t["state"] == "WIN" else 1), resets=t["resets"])
            meta = {k: v for k, v in run.items() if k != "steps"}
            jsonschema.validate(meta, _schema("meta"))
            return httpx.Response(200, json=meta)
        if req.method == "GET" and p == "/runs":
            return httpx.Response(200, json=[{k: v for k, v in r.items() if k != "steps"} for r in self.runs.values()])
        return httpx.Response(404)


@pytest.fixture
def server():
    return FakeServer()


def client(server):
    return HttpClient("http://fake", transport=httpx.MockTransport(server), backoff=0)


def test_model_run_over_http_matches_contract(server):
    c = client(server)
    c.list_games("dev")
    m = {"id": "mock", "display_name": "mock", "provider": "mock", "api_model": "mock", "input_modes": ["text"],
         "price_in": 1.0, "price_out": 1.0}
    r = play_model(c, "mock-s1-l3", MockProvider(m), m, effort=None, run_key="rk1",
                   budgets=Budgets(max_actions=15))
    assert r.actions == 15
    run = server.runs[r.run_id]
    assert run["outcome"] == "BUDGET" and run["collection"] == "dev" and run["harness_version"] == "h1"
    assert all(s["hypothesis"] for s in run["steps"])


@pytest.mark.parametrize("name", ["random", "optimal", "noop", "stop_early"])
def test_baselines_over_http(server, name):
    r = BASELINES[name](client(server), "mock-s2-l3", run_key=f"b-{name}", max_actions=50)
    meta = server.runs[r.run_id]
    assert meta["outcome"] == ("WIN" if name == "optimal" else meta["outcome"])
    if name in ("noop", "stop_early"):
        assert meta["outcome"] == "ABORTED" and meta["levels_completed"] == 0


def test_conflict_on_finished_run_key(server):
    c = client(server)
    BASELINES["noop"](c, "mock-s0-l3", run_key="same")
    with pytest.raises(AlreadyFinished):
        BASELINES["noop"](c, "mock-s0-l3", run_key="same")
    assert "same" in c.finished_run_keys()


def test_retries_5xx_then_succeeds():
    calls = {"n": 0}
    inner = FakeServer()

    def flaky(req):
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(503)
        return inner(req)

    c = HttpClient("http://fake", transport=httpx.MockTransport(flaky), backoff=0)
    assert len(c.list_games("dev")) == 5


def test_4xx_is_not_retried():
    calls = {"n": 0}

    def bad(req):
        calls["n"] += 1
        return httpx.Response(400)

    c = HttpClient("http://fake", transport=httpx.MockTransport(bad), backoff=0)
    with pytest.raises(httpx.HTTPStatusError):
        c.describe("x")
    assert calls["n"] == 1
