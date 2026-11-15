"""Trace recorder. The only writer of $DATA_DIR/runs/<run_id>/{meta.json,steps.jsonl}.

meta.json is rewritten atomically (tmp + os.replace); steps.jsonl is append-only, one line per step.
Thread-safe: a per-run lock guards writes, a global lock guards the in-memory index.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from . import config


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _atomic_write_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp{uuid.uuid4().hex[:6]}")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    os.replace(tmp, path)


class Recorder:
    def __init__(self, runs_dir: Optional[Path] = None, readonly: bool = False):
        self.runs_dir = Path(runs_dir or config.RUNS_DIR)
        self.readonly = readonly
        if not readonly:
            self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._run_locks: dict[str, threading.Lock] = {}
        self._metas: dict[str, dict] = {}
        self.listeners: list[Callable[[dict], None]] = []
        self._load_index()

    # ---------- index ----------
    def _load_index(self) -> None:
        for meta_path in self.runs_dir.glob("*/meta.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 - half-written or corrupt; skip
                continue
            if meta.get("outcome") == "IN_PROGRESS" and not self.readonly:
                # server restarted mid-run: the session is gone, close the run as aborted
                meta.update(outcome="ABORTED", end_reason="server_restart", ended_at=meta.get("ended_at") or now_iso())
                _atomic_write_json(meta_path, meta)
            self._metas[meta["run_id"]] = meta

    def finished_run_for_key(self, run_key: str) -> Optional[dict]:
        with self._lock:
            for m in self._metas.values():
                if m.get("run_key") == run_key and m.get("ended_at") and m.get("outcome") != "ABORTED":
                    return m
        return None

    def list(self, **filters: Any) -> list[dict]:
        limit = int(filters.pop("limit", 500) or 500)
        with self._lock:
            metas = list(self._metas.values())
        out = []
        for m in metas:
            if filters.get("game_id") and m.get("game_id") != filters["game_id"]:
                continue
            if filters.get("model_id") and m.get("player", {}).get("model_id") != filters["model_id"]:
                continue
            if filters.get("kind") and m.get("player", {}).get("kind") != filters["kind"]:
                continue
            if filters.get("collection") and m.get("collection") != filters["collection"]:
                continue
            if filters.get("run_key") and m.get("run_key") != filters["run_key"]:
                continue
            out.append(m)
        out.sort(key=lambda m: m.get("started_at", ""), reverse=True)
        return out[:limit]

    def get(self, run_id: str) -> Optional[dict]:
        with self._lock:
            m = self._metas.get(run_id)
            return dict(m) if m else None

    def run_dir(self, run_id: str) -> Path:
        if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
            raise KeyError(run_id)
        return self.runs_dir / run_id

    def steps(self, run_id: str) -> list[dict]:
        p = self.run_dir(run_id) / "steps.jsonl"
        if not p.exists():
            raise KeyError(run_id)
        out = []
        with self._run_lock(run_id):
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        break  # torn last line after a crash
        return out

    # ---------- writes ----------
    def _run_lock(self, run_id: str) -> threading.Lock:
        with self._lock:
            return self._run_locks.setdefault(run_id, threading.Lock())

    def start(self, meta: dict, first_step: dict) -> dict:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        run_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
        meta = {
            "run_id": run_id, "run_key": None, "collection": None, "split": None, "harness_version": None,
            "engine_version": None, **meta,
            "started_at": now_iso(), "ended_at": None, "outcome": "IN_PROGRESS", "end_reason": None,
            "levels_completed": 0, "actions": 0, "resets": 0,
            "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wall_s": 0.0,
        }
        d = self.run_dir(run_id)
        d.mkdir(parents=True)
        with self._run_lock(run_id):
            _atomic_write_json(d / "meta.json", meta)
            self._append(run_id, first_step)
        with self._lock:
            self._metas[run_id] = meta
        self._emit({"run_id": run_id, "event": "started", "meta": meta})
        self._emit({"run_id": run_id, "step": first_step})
        return meta

    def _append(self, run_id: str, step: dict) -> None:
        with open(self.run_dir(run_id) / "steps.jsonl", "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(step, separators=(",", ":")) + "\n")
            f.flush()

    def step(self, run_id: str, step: dict, meta_update: dict) -> None:
        with self._run_lock(run_id):
            self._append(run_id, step)
            with self._lock:
                self._metas[run_id].update(meta_update)
                meta = dict(self._metas[run_id])
            # meta is cheap to rewrite and keeps listings correct after a crash
            _atomic_write_json(self.run_dir(run_id) / "meta.json", meta)
        self._emit({"run_id": run_id, "step": step})

    def end(self, run_id: str, meta_update: dict) -> dict:
        with self._run_lock(run_id):
            with self._lock:
                self._metas[run_id].update(meta_update, ended_at=now_iso())
                meta = dict(self._metas[run_id])
            _atomic_write_json(self.run_dir(run_id) / "meta.json", meta)
        self._emit({"run_id": run_id, "event": "ended", "meta": meta})
        return meta

    def _emit(self, msg: dict) -> None:
        for fn in list(self.listeners):
            try:
                fn(msg)
            except Exception:  # noqa: BLE001 - a broken listener never breaks recording
                pass

    # ---------- export ----------
    def finished_since(self, since: Optional[str]) -> list[dict]:
        cutoff = parse_iso(since) if since else None
        out = []
        for m in self.list(limit=10**9):
            if not m.get("ended_at"):
                continue
            if cutoff and parse_iso(m["ended_at"]) <= cutoff:
                continue
            out.append(m)
        return out
