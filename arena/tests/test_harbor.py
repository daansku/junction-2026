"""Harbor packaging: sidecar scoring + lockdown, and the exported task layout."""
import asyncio
import json
from pathlib import Path

import pytest

from arena.engine_adapter import load_engine
from arena.harbor.sidecar import Episode, build

eng, ENGINE = load_engine()
needs_engine = pytest.mark.skipif(ENGINE != "engine", reason="needs A1's engine")
ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "data" / "collections" / "dev.json"


def episode():
    gid = eng.list_games(DEV)[0]["game_id"]
    g = eng.load_game(DEV, gid)
    return Episode(g, [lv["optimal_moves"] for lv in g.describe()["levels"]]), g.describe()


def call(mcp, tool, args=None):
    return asyncio.run(mcp.call_tool(tool, args or {}))


@needs_engine
def test_optimal_play_scores_one():
    ep, desc = episode()
    for lv in desc["levels"]:
        for a in lv["optimal_path"]:
            assert ep.act(a)[2] is None
    s = ep.score()
    assert s["won"] and s["reward"] == 1.0 and s["levels_solved"] == s["levels_total"]


@needs_engine
def test_nothing_and_stop_early_score_zero():
    ep, desc = episode()
    assert ep.score()["reward"] == 0.0
    for a in desc["levels"][0]["optimal_path"][:-1]:  # stop one move short of finishing level 1
        ep.act(a)
    assert ep.score()["reward"] == 0.0


@needs_engine
def test_partial_and_inefficient_play_scores_partially():
    ep, desc = episode()
    p = desc["levels"][0]["optimal_path"]
    ep.act("RESET")                      # wasted action counts against level 1
    for a in p:
        ep.act(a)
    s = ep.score()
    n = s["levels_total"]
    assert s["levels_solved"] == 1
    assert s["reward"] == pytest.approx((len(p) / (len(p) + 1)) / n, abs=1e-4)


@needs_engine
def test_invalid_actions_and_after_win_do_not_count():
    ep, desc = episode()
    for bad in ["JUMP", "", "ACTION9", "action1; rm -rf /"]:
        assert ep.act(bad)[2]
    assert ep.total == 0 and ep.invalid == 4
    for lv in desc["levels"]:
        for a in lv["optimal_path"]:
            ep.act(a)
    before = ep.total
    assert ep.act("ACTION1")[2] == "the game is over"
    assert ep.total == before and ep.score()["reward"] == 1.0


@needs_engine
def test_mcp_surface_is_only_observe_and_act():
    ep, _ = episode()
    mcp = build(ep, token="t0k")
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"observe", "act"}
    out = call(mcp, "act", {"action": "ACTION1"})
    text = json.dumps([getattr(c, "text", "") for c in (out[0] if isinstance(out, tuple) else out)])
    for leak in ("optimal", "budget", "rule", "level", "score", "WIN", "truth"):
        assert leak not in text


@needs_engine
def test_score_route_requires_token():
    from starlette.testclient import TestClient
    ep, _ = episode()
    app = build(ep, token="secret-token").streamable_http_app()
    with TestClient(app) as c:
        assert c.get("/score").status_code == 403
        assert c.get("/score?token=wrong").status_code == 403
        r = c.get("/score?token=secret-token")
        assert r.status_code == 200 and r.json()["reward"] == 0.0
        assert c.get("/healthz").json() == {"ok": True}


@needs_engine
def test_export_layout(tmp_path):
    from arena.harbor.export import export
    made = export(str(DEV), tmp_path, first=2, log=lambda *_: None)
    assert len(made) == 2
    t = made[0]
    for f in ["task.toml", "instruction.md", "environment/Dockerfile", "environment/docker-compose.yaml",
              "environment/game/Dockerfile", "environment/game/collection.json", "environment/game/arena/harbor/sidecar.py",
              "environment/game/engine/__init__.py", "tests/test.sh", "solution/solve.sh"]:
        assert (t / f).exists(), f
    toml = (t / "task.toml").read_text()
    assert '[[environment.mcp_servers]]' in toml and 'url = "http://game:8000/mcp"' in toml
    # token: same in compose and verifier, absent from everything the agent can see
    compose = (t / "environment/docker-compose.yaml").read_text()
    token = compose.split('SCORE_TOKEN: "')[1].split('"')[0]
    assert token in (t / "tests/test.sh").read_text()
    assert token not in (t / "instruction.md").read_text() + toml + (t / "environment/Dockerfile").read_text()
    # tokens differ per task
    assert token not in (made[1] / "environment/docker-compose.yaml").read_text()
    # the agent container gets no game code or optimal path
    assert "COPY" not in (t / "environment/Dockerfile").read_text()
    assert "optimal" not in (t / "instruction.md").read_text()
    one = json.loads((t / "environment/game/collection.json").read_text())
    assert len(one["games"]) == 1
    # shell scripts must have LF line endings to run in Linux containers
    assert b"\r\n" not in (t / "tests/test.sh").read_bytes()
