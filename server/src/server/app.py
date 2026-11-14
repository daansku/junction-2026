"""FastAPI app: REST under /api (contracts/openapi.yaml), WS /api/live, built web app at /."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import subprocess
import sys
import tarfile
from contextlib import asynccontextmanager
from typing import Any, Literal, Optional

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import config, engine_adapter
from .recorder import Recorder
from .sessions import SessionError, SessionManager

log = logging.getLogger("server")


# ---------------------------------------------------------------- live hub
class LiveHub:
    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.queues: set[asyncio.Queue] = set()

    def publish(self, msg: dict) -> None:  # called from worker threads
        if self.loop is None or not self.queues:
            return
        self.loop.call_soon_threadsafe(self._fanout, msg)

    def _fanout(self, msg: dict) -> None:
        for q in list(self.queues):
            if q.qsize() < 1000:  # slow consumer: drop rather than grow without bound
                q.put_nowait(msg)


# ---------------------------------------------------------------- models
class PlayerIn(BaseModel):
    kind: Literal["human", "model", "baseline"]
    name: str = Field(min_length=1, max_length=200)
    model_id: Optional[str] = None
    provider: Optional[str] = None
    effort: Optional[str] = None

    model_config = {"extra": "allow"}  # harness extras (harness_version, input_modes, ...) are kept in meta


class StartIn(BaseModel):
    game_id: str = Field(min_length=1, max_length=200)
    player: PlayerIn
    collection: Optional[str] = Field(default=None, max_length=100)
    run_key: Optional[str] = Field(default=None, max_length=200)
    harness_version: Optional[str] = Field(default=None, max_length=50)


class UsageIn(BaseModel):
    in_: int = Field(default=0, alias="in", ge=0)
    out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)

    model_config = {"populate_by_name": True}

    def as_dict(self) -> dict:
        return {"in": self.in_, "out": self.out, "cost_usd": self.cost_usd}


class ActIn(BaseModel):
    action: str = Field(max_length=20)
    x: Optional[int] = None
    y: Optional[int] = None
    reasoning: Optional[str] = None
    hypothesis: Optional[str] = None
    belief: Optional[str] = None
    usage: Optional[UsageIn] = None
    latency_ms: Optional[int] = Field(default=None, ge=0)


class EndIn(BaseModel):
    reason: str = Field(default="", max_length=500)
    outcome: Optional[Literal["WIN", "GAME_OVER", "BUDGET", "ABORTED"]] = None
    usage_total: Optional[UsageIn] = None


# ---------------------------------------------------------------- app
def create_app(runs_dir=None) -> FastAPI:
    recorder = Recorder(runs_dir)
    sessions = SessionManager(recorder)
    # published mode: /runs reads the committed snapshot; visitor plays are recorded to DATA_DIR only
    runs_view = Recorder(config.PUBLISHED_DIR / "runs", readonly=True) if config.PUBLISHED_MODE else recorder
    hub = LiveHub()
    recorder.listeners.append(hub.publish)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        hub.loop = asyncio.get_running_loop()

        async def idle_sweeper():
            while True:
                await asyncio.sleep(60)
                await asyncio.to_thread(sessions.sweep_idle)

        task = asyncio.create_task(idle_sweeper())
        log.info("server up: engine=%s data_dir=%s published=%s", engine_adapter.engine_name(),
                 config.DATA_DIR, config.PUBLISHED_MODE)
        yield
        task.cancel()

    app = FastAPI(title="junction-2026 game server", version="1.0.0", lifespan=lifespan)
    app.state.recorder, app.state.sessions, app.state.hub = recorder, sessions, hub
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(SessionError)
    async def _session_error(_: Request, e: SessionError):
        return JSONResponse({"detail": e.detail}, status_code=e.status)

    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health():
        return {"ok": True, "engine": engine_adapter.engine_name(), "engine_version": engine_adapter.engine_version(),
                "published_mode": config.PUBLISHED_MODE, "active_sessions": sessions.active()}

    # ---- catalogue
    @api.get("/collections")
    def collections():
        return engine_adapter.collections()

    @api.get("/games")
    def games(collection: str = "dev"):
        out = engine_adapter.list_games(collection)
        for g in out:
            g.setdefault("thumbnail_url", f"/api/games/{g['game_id']}/thumbnail.png")
        return out

    def _game(game_id: str, collection: Optional[str]):
        try:
            return engine_adapter.load_game(game_id, collection)
        except KeyError:
            raise HTTPException(404, f"unknown game {game_id}") from None

    @api.get("/games/{game_id}")
    def game_detail(game_id: str, collection: Optional[str] = None):
        return _game(game_id, collection).describe()

    @api.get("/games/{game_id}/thumbnail.png")
    def thumbnail(game_id: str, collection: Optional[str] = None, level: int = Query(1, ge=1, le=50)):
        g = _game(game_id, collection)
        frame = list(g.reset())
        if level > 1:  # walk the optimal path to reach the requested level
            for lv in g.describe()["levels"][: level - 1]:
                for a in lv["optimal_path"]:
                    frame = list(g.step(a))
        png = engine_adapter.render_png(frame, scale=4)
        return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    # ---- sessions
    @api.post("/sessions")
    def start(body: StartIn):
        player = body.player.model_dump()
        if config.PUBLISHED_MODE and player["kind"] != "human":
            raise HTTPException(403, "published mode: only human play")
        return sessions.start(body.game_id, player, body.collection, body.run_key,
                              body.harness_version or player.get("harness_version"))

    @api.post("/sessions/{session_id}/act")
    def act(session_id: str, body: ActIn):
        return sessions.act(session_id, body.action, body.x, body.y, body.reasoning, body.hypothesis, body.belief,
                            body.usage.as_dict() if body.usage else None, body.latency_ms)

    @api.get("/sessions/{session_id}/truth")
    def truth(session_id: str):
        return sessions.truth(session_id)

    @api.get("/sessions/{session_id}/frame")
    def frame(session_id: str):
        return sessions.frame(session_id)

    @api.post("/sessions/{session_id}/end")
    def end(session_id: str, body: Optional[EndIn] = None):
        body = body or EndIn()
        return sessions.end(session_id, body.reason, body.outcome,
                            body.usage_total.as_dict() if body.usage_total else None)

    # ---- runs
    @api.get("/runs")
    def runs(game_id: Optional[str] = None, model_id: Optional[str] = None, kind: Optional[str] = None,
             collection: Optional[str] = None, run_key: Optional[str] = None, limit: int = Query(500, ge=1, le=100000)):
        return runs_view.list(game_id=game_id, model_id=model_id, kind=kind, collection=collection,
                             run_key=run_key, limit=limit)

    @api.get("/runs/export")
    def export(since: Optional[str] = None):
        try:
            metas = runs_view.finished_since(since)
        except ValueError:
            raise HTTPException(422, "since must be an ISO 8601 time") from None
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for m in metas:
                d = runs_view.run_dir(m["run_id"])
                for name in ("meta.json", "steps.jsonl"):
                    p = d / name
                    if p.exists():
                        tar.add(p, arcname=f"{m['run_id']}/{name}")
        return Response(buf.getvalue(), media_type="application/gzip",
                        headers={"Content-Disposition": "attachment; filename=runs.tar.gz",
                                 "X-Run-Count": str(len(metas))})

    @api.get("/runs/{run_id}")
    def run_meta(run_id: str):
        m = runs_view.get(run_id)
        if m is None:
            raise HTTPException(404, "unknown run")
        return m

    @api.get("/runs/{run_id}/steps")
    def run_steps(run_id: str):
        try:
            return runs_view.steps(run_id)
        except KeyError:
            raise HTTPException(404, "unknown run") from None

    # ---- derived
    @api.get("/derived/{name}.json")
    def derived(name: str):
        if not name.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(404, "not found")
        dirs = ([config.PUBLISHED_DIR / "derived", config.PUBLISHED_DIR] if config.PUBLISHED_MODE
                else [config.DERIVED_DIR, config.PUBLISHED_DIR / "derived"])
        for d in dirs + [config.FIXTURES_DIR / "derived"]:
            p = d / f"{name}.json"
            if p.exists():
                return FileResponse(p, media_type="application/json", headers={"Cache-Control": "no-cache"})
        raise HTTPException(404, f"{name}.json not built yet")

    @api.post("/admin/rebuild")
    def rebuild(authorization: str = Header(default="")):
        if config.PUBLISHED_MODE:
            raise HTTPException(403, "published mode is read-only")
        if not config.ADMIN_TOKEN or authorization != f"Bearer {config.ADMIN_TOKEN}":
            raise HTTPException(401, "bad token")
        proc = subprocess.run([sys.executable, "-m", "analysis", "build", "--runs", str(recorder.runs_dir),
                               "--out", str(config.DERIVED_DIR)], capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise HTTPException(500, f"analysis build failed: {proc.stderr[-2000:]}")
        return {"ok": True, "stdout": proc.stdout[-2000:]}

    # ---- live
    @api.websocket("/live")
    async def live(ws: WebSocket):
        await ws.accept()
        q: asyncio.Queue = asyncio.Queue()
        hub.queues.add(q)
        try:
            while True:
                msg = await q.get()
                await ws.send_text(json.dumps(msg, separators=(",", ":")))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.queues.discard(q)

    app.include_router(api)

    # ---- built web app (SPA fallback)
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        dist = config.WEB_DIST
        if path.startswith("api/"):
            raise HTTPException(404, "not found")
        if dist.exists():
            target = (dist / path).resolve()
            if path and target.is_file() and dist.resolve() in target.parents:
                return FileResponse(target)
            index = dist / "index.html"
            if index.exists():
                return FileResponse(index)
        return JSONResponse({"service": "junction-2026 game server", "api": "/api", "docs": "/docs",
                             "web": "not built (run make web-build)"})

    return app


app = create_app()
