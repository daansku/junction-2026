"""Sweep runner: yaml -> list of runs -> concurrent execution with resume and a cost gate.

    python -m arena run sweeps/smoke.yaml --dry-run
    python -m arena run sweeps/smoke.yaml --api mock
    python -m arena run sweeps/main.yaml --approve-cost 40
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from .agent_loop import HARNESS_VERSION, Budgets, play_model
from .baselines import BASELINES
from .client import AlreadyFinished, make_client
from .cost import est_tokens_per_step, price
from .frames import _repo_root
from .providers import get_provider
from .registry import load_models, usable

DEFAULT_CAP = 5.0


def run_key(collection, game_id, model_id, effort, harness_version, attempt) -> str:
    s = "|".join(str(x) for x in (collection, game_id, model_id, effort, harness_version, attempt))
    return hashlib.sha1(s.encode()).hexdigest()


def spend_cap() -> float:
    """Per-sweep cap from coordination/DECISIONS.md (humans own it); default $5."""
    p = _repo_root() / "coordination" / "DECISIONS.md"
    try:
        m = re.search(r"Spend cap per sweep:\s*\$?\s*([0-9.]+)", p.read_text())
        return float(m.group(1)) if m else DEFAULT_CAP
    except OSError:
        return DEFAULT_CAP


@dataclass
class Job:
    kind: str           # "model" | baseline name
    model_id: str
    effort: str | None
    game_id: str
    attempt: int
    key: str
    est_cost: float | None = None


def load_sweep(path: str) -> dict:
    sw = yaml.safe_load(Path(path).read_text())
    sw.setdefault("name", Path(path).stem)
    sw.setdefault("collection", "dev")
    sw.setdefault("attempts", 1)
    sw.setdefault("concurrency", 4)
    sw.setdefault("models", [])
    sw.setdefault("baselines", [])
    sw.setdefault("budgets", {})
    return sw


def plan(sw: dict, client, models: dict) -> tuple[list[Job], list[str]]:
    warnings = []
    games = sw.get("games", "all")
    if games == "all" or isinstance(games, dict):
        listed = [g["game_id"] for g in client.list_games(sw["collection"])]
        games = listed[: games.get("first", len(listed))] if isinstance(games, dict) else listed
    b = Budgets(**sw["budgets"])
    jobs = []
    for spec in sw["models"]:
        spec = {"id": spec} if isinstance(spec, str) else spec
        m = models.get(spec["id"])
        if m is None:
            warnings.append(f"unknown model {spec['id']} (not in models.yaml) - skipped")
            continue
        if not usable(m):
            warnings.append(f"model {m['id']} not verified / no api_model yet - skipped")
            continue
        if m.get("test_only") and sw.get("api") not in ("mock", None) and not sw.get("allow_test_models"):
            warnings.append(f"model {m['id']} is test-only - skipped")
            continue
        efforts = spec.get("efforts") or [spec.get("effort", m.get("default_effort"))]
        modes = spec.get("input_modes") or m.get("input_modes")
        for eff in efforts:
            for g in games:
                for att in range(sw["attempts"]):
                    tin, tout = est_tokens_per_step(m, "both" if len(modes) > 1 else modes[0], eff)
                    steps = min(b.max_actions, sw.get("est_steps_per_game", 150))
                    est = price(m, tin * steps, tout * steps)
                    if est is not None:
                        est = min(est, b.max_cost_usd)
                    jobs.append(Job("model", m["id"], eff, g, att,
                                    run_key(sw["collection"], g, m["id"], eff, HARNESS_VERSION, att), est))
    for name in sw["baselines"]:
        if name not in BASELINES:
            warnings.append(f"unknown baseline {name}")
            continue
        for g in games:
            for att in range(sw["attempts"] if name in ("random", "stop_early") else 1):
                jobs.append(Job(name, f"baseline:{name}", None, g, att,
                                run_key(sw["collection"], g, f"baseline:{name}", None, HARNESS_VERSION, att), 0.0))
    return jobs, warnings


def estimate(jobs: list[Job]) -> tuple[float, int]:
    total, unknown = 0.0, 0
    for j in jobs:
        if j.est_cost is None:
            unknown += 1
        else:
            total += j.est_cost
    return total, unknown


def execute(sw: dict, *, api: str, dry_run: bool, approve_cost: float | None, out_dir: Path, log=print) -> list[dict]:
    models = load_models()
    sw["api"] = api
    ledger = out_dir / "mock_ledger.jsonl" if api == "mock" else None
    client = make_client(api, ledger=ledger)
    jobs, warnings = plan(sw, client, models)
    for w in warnings:
        log(f"warning: {w}")
    done = client.finished_run_keys()
    todo = [j for j in jobs if j.key not in done]
    total, unknown = estimate(todo)
    log(f"sweep {sw['name']}: {len(jobs)} runs, {len(jobs) - len(todo)} already finished, {len(todo)} to run")
    by_model: dict[str, list[Job]] = {}
    for j in todo:
        by_model.setdefault(f"{j.model_id}@{j.effort}" if j.kind == "model" else j.model_id, []).append(j)
    for k, js in sorted(by_model.items()):
        c = sum(j.est_cost or 0 for j in js)
        log(f"  {k:<40} {len(js):>4} runs   est ${c:,.2f}" + ("  (price unknown)" if any(j.est_cost is None for j in js) else ""))
    cap = spend_cap()
    log(f"estimated cost: ${total:,.2f}" + (f" + {unknown} runs with unknown price" if unknown else "")
        + f"   (cap ${cap:,.2f} per sweep from DECISIONS.md)")
    if dry_run:
        return []
    if total > cap and (approve_cost is None or approve_cost < total):
        raise SystemExit(f"estimate ${total:,.2f} exceeds cap ${cap:,.2f}; get human approval and rerun "
                         f"with --approve-cost {total:.0f}")

    budgets = Budgets(**sw["budgets"])
    sems = {mid: threading.Semaphore(models[mid].get("max_concurrency", 4)) for mid in models}
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / f"{sw['name']}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    lock = threading.Lock()
    rows: list[dict] = []

    def one(j: Job):
        if j.kind == "model":
            m = models[j.model_id]
            with sems[j.model_id]:
                res = play_model(client, j.game_id, get_provider(m), m, effort=j.effort, run_key=j.key,
                                 budgets=budgets, input_modes=None)
        else:
            res = BASELINES[j.kind](client, j.game_id, run_key=j.key, seed=j.attempt,
                                    max_actions=budgets.max_actions)
        row = {"sweep": sw["name"], "collection": sw["collection"], "model_id": j.model_id, "effort": j.effort,
               "attempt": j.attempt, "run_key": j.key, "harness_version": HARNESS_VERSION, **asdict(res)}
        with lock:
            rows.append(row)
            with results_path.open("a") as f:
                f.write(json.dumps(row) + "\n")
        log(f"  done {j.model_id}@{j.effort} {j.game_id}#{j.attempt}: {res.outcome} "
            f"{res.levels_completed}/{res.levels_total} lv, {res.actions} act, ${res.cost_usd:.3f}")
        return row

    with cf.ThreadPoolExecutor(max_workers=sw["concurrency"]) as ex:
        futs = [ex.submit(one, j) for j in todo]
        for f in cf.as_completed(futs):
            try:
                f.result()
            except AlreadyFinished:
                log("  skipped: server says this run_key already finished")
            except Exception as e:  # one broken run must not kill the sweep; it stays unfinished -> rerun
                log(f"  run failed: {type(e).__name__}: {e}")
    log(f"results: {results_path}")
    return rows
