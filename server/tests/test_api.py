import io
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from server.app import create_app

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "contracts" / "trace.schema.json").read_text())


def validate(obj, name):
    jsonschema.validate(obj, {"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]})


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(tmp_path / "runs")) as c:
        yield c


def first_game(c):
    games = c.get("/api/games").json()
    assert len(games) >= 3
    return games[0]["game_id"]


def start(c, game_id, **kw):
    body = {"game_id": game_id, "player": {"kind": "baseline", "name": "optimal"}, **kw}
    r = c.post("/api/sessions", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["engine"] == "fake"


def test_play_optimal_to_win_and_trace(client):
    gid = first_game(client)
    desc = client.get(f"/api/games/{gid}").json()
    s = start(client, gid, run_key="k1")
    assert set(s) == {"session_id", "run_id", "frame", "available_actions"}
    assert len(s["frame"]) == 64 and all(len(r) == 64 for r in s["frame"])
    n = 0
    for lv in desc["levels"]:
        for a in lv["optimal_path"]:
            r = client.post(f"/api/sessions/{s['session_id']}/act", json={"action": a, "reasoning": "go"})
            assert r.status_code == 200
            assert set(r.json()) == {"frame", "available_actions"}  # pixels only
            n += 1
    assert client.get(f"/api/sessions/{s['session_id']}/truth").json()["state"] == "WIN"
    meta = client.post(f"/api/sessions/{s['session_id']}/end", json={"reason": "done"}).json()
    assert meta["outcome"] == "WIN" and meta["actions"] == n and meta["levels_completed"] == desc["levels_total"]
    validate(meta, "meta")
    steps = client.get(f"/api/runs/{s['run_id']}/steps").json()
    assert len(steps) == n + 1 and steps[0]["action"] is None
    for st in steps:
        validate(st, "step")
    assert client.get("/api/runs", params={"run_key": "k1"}).json()[0]["run_id"] == s["run_id"]
    # finished run_key cannot be reused
    r = client.post("/api/sessions", json={"game_id": gid, "player": {"kind": "baseline", "name": "x"}, "run_key": "k1"})
    assert r.status_code == 409
    # export
    r = client.get("/api/runs/export")
    names = tarfile.open(fileobj=io.BytesIO(r.content)).getnames()
    assert f"{s['run_id']}/steps.jsonl" in names


def test_bad_inputs(client):
    assert client.post("/api/sessions", json={"game_id": "nope", "player": {"kind": "human", "name": "a"}}).status_code == 404
    assert client.post("/api/sessions", json={"game_id": "x", "player": {"kind": "alien", "name": "a"}}).status_code == 422
    s = start(client, first_game(client))
    sid = s["session_id"]
    assert client.post(f"/api/sessions/{sid}/act", json={"action": "JUMP"}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/act", json={"action": "ACTION6", "x": 99, "y": 0}).status_code == 422
    assert client.post("/api/sessions/nope/act", json={"action": "ACTION1"}).status_code == 404
    # unavailable action is a recorded no-op
    r = client.post(f"/api/sessions/{sid}/act", json={"action": "ACTION7"})
    assert r.status_code == 200 and r.json()["frame"] == s["frame"]
    client.post(f"/api/sessions/{sid}/end", json={"reason": "stop"})
    assert client.post(f"/api/sessions/{sid}/act", json={"action": "ACTION1"}).status_code == 404
    assert client.get("/api/runs/..%2F..%2Fetc/steps").status_code == 404


def test_end_outcomes(client):
    gid = first_game(client)
    s = start(client, gid)
    assert client.post(f"/api/sessions/{s['session_id']}/end", json={"reason": "budget_actions"}).json()["outcome"] == "BUDGET"
    s = start(client, gid)
    assert client.post(f"/api/sessions/{s['session_id']}/end", json={}).json()["outcome"] == "ABORTED"


def test_parallel_sessions(client):
    gid = first_game(client)

    def play(i):
        s = start(client, gid)
        for _ in range(20):
            client.post(f"/api/sessions/{s['session_id']}/act", json={"action": ["ACTION1", "ACTION2", "ACTION3", "ACTION4"][i % 4]})
        return client.post(f"/api/sessions/{s['session_id']}/end", json={"reason": "x"}).json()

    with ThreadPoolExecutor(16) as ex:
        metas = list(ex.map(play, range(32)))
    for m in metas:
        assert m["actions"] == 20
        steps = client.get(f"/api/runs/{m['run_id']}/steps").json()
        assert [s["i"] for s in steps] == list(range(21))


def test_thumbnail_and_derived(client):
    gid = first_game(client)
    r = client.get(f"/api/games/{gid}/thumbnail.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert client.get("/api/derived/missing-file.json").status_code == 404


def test_determinism():
    from server.fake_engine import DEV_SPECS, FakeGame
    a, b = FakeGame(DEV_SPECS[1]), FakeGame(DEV_SPECS[1])
    for act in ["ACTION1", "ACTION4", "ACTION2", "RESET", "ACTION3"]:
        assert a.step(act) == b.step(act)
