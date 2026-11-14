from fastapi.testclient import TestClient

from server.app import create_app
from server.challenge import clean_name


def _play(c, kind="human", name="visitor", end=True):
    gid = c.get("/api/games").json()[0]["game_id"]
    s = c.post("/api/sessions", json={"game_id": gid, "player": {"kind": kind, "name": name}}).json()
    c.post(f"/api/sessions/{s['session_id']}/act", json={"action": "ACTION1"})
    if end:
        c.post(f"/api/sessions/{s['session_id']}/end", json={"reason": "visitor quit"})
    return s["run_id"], gid


def test_score_comes_from_the_run_not_the_client(tmp_path):
    with TestClient(create_app(tmp_path / "runs")) as c:
        run_id, gid = _play(c)
        r = c.post("/api/challenge/score", json={"run_id": run_id, "name": "  Ada  ", "beat_ai": True,
                                                  "levels_completed": 99, "actions": 0})
        assert r.status_code == 200, r.text
        row = r.json()
        assert row["name"] == "Ada" and row["levels_completed"] == 0 and row["actions"] == 1 and row["rank"] == 1
        board = c.get("/api/challenge/board", params={"game_id": gid}).json()
        assert board["plays"] == 1 and board["beat_ai"] == 1 and board["rows"][0]["run_id"] == run_id
        # once per run
        assert c.post("/api/challenge/score", json={"run_id": run_id, "name": "Ada"}).status_code == 409
        # stored apart from research runs
        assert (tmp_path / "challenge" / "board.jsonl").exists()
        assert not (tmp_path / "runs" / "challenge").exists()


def test_rejects_model_runs_unfinished_runs_unknown_runs(tmp_path):
    with TestClient(create_app(tmp_path / "runs")) as c:
        model_run, _ = _play(c, kind="model", name="m")
        assert c.post("/api/challenge/score", json={"run_id": model_run, "name": "x"}).status_code == 403
        open_run, _ = _play(c, end=False)
        assert c.post("/api/challenge/score", json={"run_id": open_run, "name": "x"}).status_code == 409
        assert c.post("/api/challenge/score", json={"run_id": "nope", "name": "x"}).status_code == 404


def test_rate_limit_and_names(tmp_path):
    with TestClient(create_app(tmp_path / "runs")) as c:
        codes = []
        for i in range(8):
            run_id, _ = _play(c)
            codes.append(c.post("/api/challenge/score", json={"run_id": run_id, "name": f"p{i}"}).status_code)
        assert codes[:6] == [200] * 6 and 429 in codes[6:]
    assert clean_name("a" * 80) == "a" * 24
    assert clean_name("Zoë\n\tthe\x00 great") == "Zoë the great"
    for bad in ["   ", "visit www.example.com", "http://x", "me@mail"]:
        try:
            clean_name(bad)
            assert False, bad
        except ValueError:
            pass


def test_board_survives_restart(tmp_path):
    with TestClient(create_app(tmp_path / "runs")) as c:
        run_id, gid = _play(c)
        c.post("/api/challenge/score", json={"run_id": run_id, "name": "Bo"})
    with TestClient(create_app(tmp_path / "runs")) as c:
        assert c.get("/api/challenge/board").json()["rows"][0]["name"] == "Bo"
