"""Visitor scoreboard for the "Can you beat the AI?" demo (`/challenge`, PLAN.md section 3.4, A2-22).

Stored apart from research runs: `DATA_DIR/challenge/board.jsonl`, never under `runs/`, so the board can
never leak into the human baseline. Allowed in published mode (no paid calls, no admin power).

The score is not taken from the client. The client names the run it just played; the server reads
that run's recorded meta (levels completed, actions, outcome) and stores those numbers. The only
free input is the visitor's display name (short, printable, no URLs). `beat_ai` is the client's
verdict against the recorded model runs it showed; it is a display flag only.
"""
from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import config

NAME_MAX = 24
RATE_PER_MIN = 6            # score posts per client IP per minute
BOARD_MAX_RETURN = 100
_URLISH = re.compile(r"(https?:|www\.|\.[a-z]{2,4}/|@)", re.I)


class ScoreIn(BaseModel):
    run_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=64)
    beat_ai: bool = False


def clean_name(raw: str) -> str:
    """Printable, single-line, <= NAME_MAX chars, no links. Raises ValueError when nothing usable is left."""
    s = re.sub(r"\s", " ", unicodedata.normalize("NFKC", raw))  # tabs/newlines become spaces before control chars go
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] in "LNPZ" or ch in "-_.' ")
    s = re.sub(r"\s+", " ", s).strip()[:NAME_MAX].strip()
    if not s:
        raise ValueError("empty name")
    if _URLISH.search(s):
        raise ValueError("names cannot contain links")
    return s


class Board:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else config.DATA_DIR / "challenge" / "board.jsonl"
        self._lock = threading.Lock()
        self._rows: list[dict] = []
        self._by_run: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a torn last line after a crash loses one row, not the board
                self._rows.append(r)
                self._by_run.add(r["run_id"])

    def add(self, row: dict) -> dict:
        with self._lock:
            if row["run_id"] in self._by_run:
                raise HTTPException(409, "this run is already on the board")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            self._rows.append(row)
            self._by_run.add(row["run_id"])
            return row

    def top(self, game_id: Optional[str], limit: int) -> list[dict]:
        with self._lock:
            rows = [r for r in self._rows if game_id is None or r["game_id"] == game_id]
        # more levels first, then fewer actions, then earlier
        rows.sort(key=lambda r: (-r["levels_completed"], r["actions"], r["at"]))
        return [{**r, "rank": i + 1} for i, r in enumerate(rows[:limit])]

    def stats(self, game_id: Optional[str]) -> dict:
        with self._lock:
            rows = [r for r in self._rows if game_id is None or r["game_id"] == game_id]
        return {"plays": len(rows), "beat_ai": sum(1 for r in rows if r.get("beat_ai")),
                "wins": sum(1 for r in rows if r["outcome"] == "WIN")}


def router(recorder, board: Optional[Board] = None) -> APIRouter:
    r = APIRouter(prefix="/challenge", tags=["challenge"])
    b = board or Board()
    hits: dict[str, list[float]] = {}

    @r.post("/score")
    def post_score(body: ScoreIn, request: Request):
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        recent = [t for t in hits.get(ip, []) if now - t < 60]
        if len(recent) >= RATE_PER_MIN:
            raise HTTPException(429, "too many scores from here; wait a minute")
        hits[ip] = recent + [now]
        if len(hits) > 10_000:
            hits.clear()
        try:
            name = clean_name(body.name)
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        meta = recorder.get(body.run_id)
        if meta is None:
            raise HTTPException(404, "unknown run")
        if (meta.get("player") or {}).get("kind") != "human":
            raise HTTPException(403, "only human runs can be posted")
        if meta.get("outcome") == "IN_PROGRESS":
            raise HTTPException(409, "finish (or end) the run first")
        row = {"run_id": meta["run_id"], "game_id": meta["game_id"], "name": name,
               "levels_completed": int(meta.get("levels_completed") or 0), "levels_total": int(meta.get("levels_total") or 0),
               "actions": int(meta.get("actions") or 0), "outcome": meta.get("outcome"), "beat_ai": bool(body.beat_ai),
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        row = b.add(row)
        rank = next((x["rank"] for x in b.top(row["game_id"], 10**9) if x["run_id"] == row["run_id"]), None)
        return {**row, "rank": rank}

    @r.get("/board")
    def get_board(game_id: Optional[str] = Query(None, max_length=100), limit: int = Query(20, ge=1, le=BOARD_MAX_RETURN)):
        return {"game_id": game_id, "rows": b.top(game_id, limit), **b.stats(game_id)}

    return r
