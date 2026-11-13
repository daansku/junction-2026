"""Session core shared by REST and MCP. Holds live games in memory, records every step.

Model-facing return values are pixels only: frame + available_actions. Truth is separate.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from . import config, engine_adapter
from .recorder import Recorder

VALID_ACTIONS = {"RESET", "ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION6", "ACTION7"}
END_OUTCOMES = {"WIN", "GAME_OVER", "BUDGET", "ABORTED"}


class SessionError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


@dataclass
class Session:
    session_id: str
    run_id: str
    game: Any
    game_id: str
    started: float
    last_seen: float
    lock: threading.Lock = field(default_factory=threading.Lock)
    actions: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    ended: bool = False


def _available(game) -> list[str]:
    return [getattr(a, "value", a) for a in game.available_actions()]


def _frame(game) -> list[str]:
    return list(game.frame())


def _levels_completed(truth: dict) -> int:
    return int(truth.get("level", 1)) - 1 + (1 if truth.get("state") == "WIN" else 0)


class SessionManager:
    def __init__(self, recorder: Recorder):
        self.recorder = recorder
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    # ---------- lifecycle ----------
    def start(self, game_id: str, player: dict, collection: Optional[str] = None,
              run_key: Optional[str] = None, harness_version: Optional[str] = None) -> dict:
        kind = player.get("kind")
        if kind not in ("human", "model", "baseline") or not str(player.get("name", "")).strip():
            raise SessionError(422, "player.kind must be human|model|baseline and player.name non-empty")
        if run_key and self.recorder.finished_run_for_key(run_key):
            raise SessionError(409, f"run_key {run_key} already has a finished run")
        try:
            game = engine_adapter.load_game(game_id, collection)
        except KeyError:
            raise SessionError(404, f"unknown game {game_id}") from None
        frame = list(game.reset())
        truth = game.truth()
        player = {"kind": kind, "name": str(player["name"])[:200], "model_id": player.get("model_id"),
                  "provider": player.get("provider"), "effort": player.get("effort")}
        meta = self.recorder.start(
            {"run_key": run_key, "game_id": game_id, "collection": collection, "player": player,
             "harness_version": harness_version, "engine_version": engine_adapter.engine_version(),
             "levels_total": truth.get("levels_total", 1)},
            {"i": 0, "t_ms": 0, "action": None, "frame": frame, "truth": truth, "reasoning": None,
             "hypothesis": None, "belief": None, "usage": {"in": 0, "out": 0, "cost_usd": 0.0}, "latency_ms": None},
        )
        now = time.monotonic()
        s = Session(uuid.uuid4().hex, meta["run_id"], game, game_id, now, now)
        with self._lock:
            self._sessions[s.session_id] = s
        return {"session_id": s.session_id, "run_id": s.run_id, "frame": frame, "available_actions": _available(game)}

    def _get(self, session_id: str) -> Session:
        with self._lock:
            s = self._sessions.get(session_id)
        if s is None:
            raise SessionError(404, "unknown session")
        return s

    def act(self, session_id: str, action: str, x: Optional[int] = None, y: Optional[int] = None,
            reasoning: Optional[str] = None, hypothesis: Optional[str] = None, belief: Optional[str] = None,
            usage: Optional[dict] = None, latency_ms: Optional[int] = None) -> dict:
        s = self._get(session_id)
        action = str(action or "").strip().upper()
        if action not in VALID_ACTIONS:
            raise SessionError(422, f"invalid action {action!r}")
        if x is not None and not (0 <= int(x) <= 63) or y is not None and not (0 <= int(y) <= 63):
            raise SessionError(422, "x and y must be in 0..63")
        if belief is not None and belief not in ("playing", "won", "lost"):
            belief = None
        with s.lock:
            if s.ended:
                raise SessionError(409, "session already ended")
            if s.actions >= config.MAX_ACTIONS_PER_SESSION:
                raise SessionError(409, "action limit for this session reached")
            if action not in _available(s.game):
                # unavailable actions are a no-op step: recorded, frame unchanged, still counted
                frame = _frame(s.game)
            else:
                frame = list(s.game.step(action, x, y) if action == "ACTION6" else s.game.step(action))
            truth = s.game.truth()
            s.actions += 1
            s.last_seen = time.monotonic()
            u = usage or {}
            u_in, u_out = max(0, int(u.get("in", 0) or 0)), max(0, int(u.get("out", 0) or 0))
            u_cost = max(0.0, float(u.get("cost_usd", 0) or 0))
            s.tokens_in += u_in
            s.tokens_out += u_out
            s.cost_usd += u_cost
            step = {"i": s.actions, "t_ms": int((time.monotonic() - s.started) * 1000), "action": action,
                    "x": x, "y": y, "frame": frame, "truth": truth,
                    "reasoning": _clip(reasoning), "hypothesis": _clip(hypothesis, 2000), "belief": belief,
                    "usage": {"in": u_in, "out": u_out, "cost_usd": u_cost},
                    "latency_ms": int(latency_ms) if latency_ms is not None else None}
            self.recorder.step(s.run_id, step, {
                "actions": s.actions, "resets": int(truth.get("resets", 0)),
                "levels_completed": _levels_completed(truth), "tokens_in": s.tokens_in,
                "tokens_out": s.tokens_out, "cost_usd": round(s.cost_usd, 6),
                "wall_s": round(time.monotonic() - s.started, 3)})
            return {"frame": frame, "available_actions": _available(s.game)}

    def truth(self, session_id: str) -> dict:
        s = self._get(session_id)
        with s.lock:
            return s.game.truth()

    def frame(self, session_id: str) -> dict:
        s = self._get(session_id)
        with s.lock:
            return {"frame": _frame(s.game), "available_actions": _available(s.game)}

    def end(self, session_id: str, reason: str = "", outcome: Optional[str] = None,
            usage_total: Optional[dict] = None) -> dict:
        s = self._get(session_id)
        with s.lock:
            if s.ended:
                return self.recorder.get(s.run_id) or {}
            truth = s.game.truth()
            if outcome not in END_OUTCOMES:
                outcome = None
            if outcome is None:
                state = truth.get("state")
                if state in ("WIN", "GAME_OVER"):
                    outcome = state
                elif "budget" in (reason or "").lower():
                    outcome = "BUDGET"
                else:
                    outcome = "ABORTED"
            upd = {"outcome": outcome, "end_reason": (reason or None) and str(reason)[:500],
                   "levels_completed": _levels_completed(truth), "resets": int(truth.get("resets", 0)),
                   "wall_s": round(time.monotonic() - s.started, 3)}
            if usage_total:  # harness-side totals win when the harness reports them
                upd.update(tokens_in=int(usage_total.get("in", s.tokens_in) or 0),
                           tokens_out=int(usage_total.get("out", s.tokens_out) or 0),
                           cost_usd=float(usage_total.get("cost_usd", s.cost_usd) or 0))
            s.ended = True
            meta = self.recorder.end(s.run_id, upd)
        with self._lock:
            self._sessions.pop(session_id, None)
        return meta

    def sweep_idle(self) -> int:
        cutoff = time.monotonic() - config.SESSION_IDLE_S
        with self._lock:
            stale = [sid for sid, s in self._sessions.items() if s.last_seen < cutoff]
        for sid in stale:
            try:
                self.end(sid, reason="idle_timeout")
            except SessionError:
                pass
        return len(stale)

    def active(self) -> int:
        with self._lock:
            return len(self._sessions)


def _clip(s: Optional[str], n: int = 20000) -> Optional[str]:
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n] + "…[truncated]"
