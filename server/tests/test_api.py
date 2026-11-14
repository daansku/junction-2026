import io
import os
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
    assert h["ok"] and h["engine"] == os.environ["SERVER_ENGINE"]


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


def test_live_ws(client):
    gid = first_game(client)
    with client.websocket_connect("/api/live") as ws:
        s = start(client, gid)
        client.post(f"/api/sessions/{s['session_id']}/act", json={"action": "ACTION1"})
        client.post(f"/api/sessions/{s['session_id']}/end", json={"reason": "x"})
        msgs = [json.loads(ws.receive_text()) for _ in range(4)]
    assert msgs[0]["event"] == "started" and msgs[0]["run_id"] == s["run_id"]
    assert [m.get("step", {}).get("i") for m in msgs[1:3]] == [0, 1]
    assert msgs[3]["event"] == "ended"


def test_player_extras_kept(client):
    gid = first_game(client)
    r = client.post("/api/sessions", json={"game_id": gid, "player": {
        "kind": "model", "name": "m", "model_id": "x", "harness_version": "h1", "input_modes": ["text"]}})
    meta = client.get(f"/api/runs/{r.json()['run_id']}").json()
    assert meta["player"]["input_modes"] == ["text"] and meta["harness_version"] == "h1"
    validate(meta, "meta")


def test_published_mode(tmp_path, monkeypatch):
    from server import config
    pub = tmp_path / "published"
    (pub / "runs").mkdir(parents=True)
    import shutil
    shutil.copytree(ROOT / "data" / "fixtures" / "runs" / "fixture-run-0001", pub / "runs" / "fixture-run-0001")
    monkeypatch.setattr(config, "PUBLISHED_MODE", True)
    monkeypatch.setattr(config, "PUBLISHED_DIR", pub)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "t")
    with TestClient(create_app(tmp_path / "runs")) as c:
        assert [r["run_id"] for r in c.get("/api/runs").json()] == ["fixture-run-0001"]
        assert len(c.get("/api/runs/fixture-run-0001/steps").json()) == 31
        gid = first_game(c)
        assert c.post("/api/sessions", json={"game_id": gid, "player": {"kind": "model", "name": "m"}}).status_code == 403
        s = c.post("/api/sessions", json={"game_id": gid, "player": {"kind": "human", "name": "visitor"}})
        assert s.status_code == 200
        assert c.post(f"/api/sessions/{s.json()['session_id']}/act", json={"action": "ACTION1"}).status_code == 200
        # visitor play never enters the published listing
        assert len(c.get("/api/runs").json()) == 1
        assert c.post("/api/admin/rebuild", headers={"Authorization": "Bearer t"}).status_code == 403


def test_generate_and_play(client, monkeypatch):
    from server import config
    monkeypatch.setattr(config, "ADMIN_TOKEN", "t")
    r = client.post("/api/games/generate", json={"difficulty": 1, "n_levels": 3})
    assert r.status_code == 200, r.text
    g = r.json()
    assert 1_000_000 <= g["seed"] <= 9_999_999 and g["levels_total"] == 3 and g["collection"] == "generated"
    # same seed -> same game
    assert client.post("/api/games/generate", json={"seed": g["seed"], "difficulty": 1, "n_levels": 3}).json()["game_id"] == g["game_id"]
    # playable through the normal session routes, to a win on the optimal path
    desc = client.get(f"/api/games/{g['game_id']}").json()
    s = start(client, g["game_id"])
    for lv in desc["levels"]:
        for a in lv["optimal_path"]:
            client.post(f"/api/sessions/{s['session_id']}/act", json={"action": a})
    assert client.get(f"/api/sessions/{s['session_id']}/truth").json()["state"] == "WIN"
    assert g["game_id"] in [x["game_id"] for x in client.get("/api/games", params={"collection": "generated"}).json()]
    assert client.get(f"/api/games/{g['game_id']}/thumbnail.png").status_code == 200
    # eval seeds are guarded, bad params rejected
    assert client.post("/api/games/generate", json={"seed": 900005}).status_code == 403
    assert client.post("/api/games/generate", json={"seed": 900005, "n_levels": 3},
                       headers={"Authorization": "Bearer t"}).status_code == 200
    assert client.post("/api/games/generate", json={"difficulty": 9}).status_code == 422
    assert client.post("/api/games/generate", json={"n_levels": 50}).status_code == 422
    assert client.post("/api/games/generate", json={"seed": -1}).status_code == 422


def test_ghosts_takeover_rule_images(client):
    gid = first_game(client)
    desc = client.get(f"/api/games/{gid}").json()
    # a model run: wastes 2 moves then plays optimally through level 1 and into level 2
    s = client.post("/api/sessions", json={"game_id": gid, "player": {"kind": "model", "name": "m", "model_id": "mx"}}).json()
    acts = ["RESET", "RESET"] + desc["levels"][0]["optimal_path"] + desc["levels"][1]["optimal_path"][:2]
    for a in acts:
        client.post(f"/api/sessions/{s['session_id']}/act", json={"action": a, "hypothesis": "h-" + a})
    client.post(f"/api/sessions/{s['session_id']}/end", json={"reason": "x"})

    g = client.get(f"/api/games/{gid}/ghosts", params={"level": 1}).json()
    assert g["optimal"]["actions"] == len(desc["levels"][0]["optimal_path"])
    assert len(g["optimal"]["steps"][0]["frame"]) == 64
    gh = g["ghosts"][0]
    assert gh["run_id"] == s["run_id"] and gh["solved"] is True
    assert gh["actions"] == 2 + len(desc["levels"][0]["optimal_path"])
    assert gh["steps"][0]["hypothesis"] == "h-RESET" and len(gh["start_frame"]) == 64
    g2 = client.get(f"/api/games/{gid}/ghosts", params={"level": 2, "frames": "false"}).json()
    assert g2["ghosts"][0]["solved"] is False and g2["ghosts"][0]["actions"] == 2
    assert "frame" not in g2["ghosts"][0]["steps"][0]
    assert client.get("/api/games/nope/ghosts").status_code == 404

    # take over at a step on level 2 -> new human run starts at level 2, flagged
    step_on_l2 = len(acts) - 1
    t = client.post("/api/sessions", json={"player": {"kind": "human", "name": "h"},
                                           "takeover_of": {"run_id": s["run_id"], "step": step_on_l2}})
    assert t.status_code == 200, t.text
    assert client.get(f"/api/sessions/{t.json()['session_id']}/truth").json()["level"] == 2
    meta = client.get(f"/api/runs/{t.json()['run_id']}").json()
    assert meta["start_level"] == 2 and meta["takeover_of"]["run_id"] == s["run_id"]
    validate(meta, "meta")
    # takeover runs never become ghosts
    assert all(x["run_id"] != t.json()["run_id"] for x in client.get(f"/api/games/{gid}/ghosts", params={"kind": "human"}).json()["ghosts"])
    assert client.post("/api/sessions", json={"player": {"kind": "human", "name": "h"},
                                              "takeover_of": {"run_id": "nope", "step": 1}}).status_code == 404
    assert client.post("/api/sessions", json={"game_id": gid, "start_level": 99,
                                              "player": {"kind": "human", "name": "h"}}).status_code == 422
    assert client.post("/api/sessions", json={"player": {"kind": "human", "name": "h"}}).status_code == 422

    # rule images
    r = client.get("/api/rules/img/ice.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert client.get("/api/rules/img/..%2F..%2FREADME.md").status_code == 404
    assert client.get("/api/rules/img/nope.png").status_code == 404
