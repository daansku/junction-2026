"""Judge-LLM calls for failure explanations (human plan Sat 14:10, section 2; A5 builds prompts, A3 runs calls).

    python -m arena judge --in prompts.jsonl --out replies.jsonl [--model gemini-pro] [--dry-run] [--approve-cost N]

Input (one JSON object per line, written by A5's `analysis`):
    {"id": "<run_id>:<level>", "prompt": "...", "system": "... (optional)", "max_tokens": 8000 (optional; thinking models spend part of it on hidden reasoning)}
Output (one line per input id, appended; rerun resumes by skipping ids already answered without error):
    {"id", "model", "text", "tokens_in", "tokens_out", "cost_usd", "latency_ms", "error"}

The judge may see the truth (rules, optimal path, truth events); playing models never do. This tool only sends what
A5 put in the prompt. Spend: a cost estimate is printed first, and the run refuses to go over the DECISIONS.md
per-sweep cap unless --approve-cost is given.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import threading
from pathlib import Path

from .cost import price
from .providers import get_provider
from .registry import has_key, key_env, load_models, usable

DEFAULT_MODEL = "gemini-pro"
DEFAULT_SYSTEM = ("You are an expert analyst of agents playing grid puzzle games. You are given the hidden rules, the "
                  "optimal solution and the agent's own step-by-step reasoning. Answer exactly in the format asked.")
CHARS_PER_TOKEN = 3.5


def load_prompts(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        if "id" not in r or "prompt" not in r:
            raise ValueError(f"{path}:{i}: each line needs 'id' and 'prompt'")
        rows.append(r)
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate ids")
    return rows


def done_ids(out: Path) -> set[str]:
    if not out.exists():
        return set()
    ok = set()
    for line in out.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not r.get("error"):
            ok.add(r["id"])
    return ok


def estimate(model: dict, rows: list[dict], default_max: int) -> float | None:
    tin = sum(len(r.get("system") or DEFAULT_SYSTEM) + len(r["prompt"]) for r in rows) / CHARS_PER_TOKEN
    tout = sum(r.get("max_tokens") or default_max for r in rows) * 0.5  # replies rarely use the full cap
    return price(model, int(tin), int(tout))


def run(inp: Path, out: Path, model_id: str = DEFAULT_MODEL, effort: str | None = None, max_tokens: int = 8000,
        concurrency: int = 4, dry_run: bool = False, approve_cost: float | None = None, cap: float | None = None,
        log=print) -> dict:
    models = load_models()
    if model_id not in models:
        raise SystemExit(f"unknown model {model_id}")
    m = models[model_id]
    if not usable(m):
        raise SystemExit(f"model {model_id} is not verified")
    if not has_key(m):
        raise SystemExit(f"model {model_id}: no {key_env(m)} in .env")
    rows = load_prompts(inp)
    skip = done_ids(out)
    todo = [r for r in rows if r["id"] not in skip]
    est = estimate(m, todo, max_tokens)
    log(f"judge {model_id}: {len(rows)} prompts, {len(rows) - len(todo)} already answered, {len(todo)} to send; "
        f"estimated cost {'$%.2f' % est if est is not None else 'unknown (no price)'}"
        + (f" (cap ${cap:.2f})" if cap is not None else ""))
    if dry_run or not todo:
        return {"todo": len(todo), "est_cost": est, "sent": 0}
    limit = approve_cost if approve_cost is not None else cap
    if est is not None and limit is not None and est > limit:
        raise SystemExit(f"estimated ${est:.2f} is over the cap ${limit:.2f}; rerun with --approve-cost {est:.0f} "
                         "once a human has approved it")
    prov = get_provider(m)
    lock = threading.Lock()
    out.parent.mkdir(parents=True, exist_ok=True)
    spent = 0.0

    def one(r: dict) -> dict:
        try:
            rep = prov.complete(r.get("system") or DEFAULT_SYSTEM, [{"type": "text", "text": r["prompt"]}],
                                effort=effort, max_tokens=r.get("max_tokens") or max_tokens)
            cost = price(m, rep.tokens_in, rep.tokens_out)
            return {"id": r["id"], "model": model_id, "text": rep.text, "tokens_in": rep.tokens_in,
                    "tokens_out": rep.tokens_out, "cost_usd": cost, "latency_ms": rep.latency_ms, "error": None}
        except Exception as e:  # one failed call never kills the batch; rerun retries it
            return {"id": r["id"], "model": model_id, "text": "", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                    "latency_ms": None, "error": f"{type(e).__name__}: {e}"[:500]}

    n_err = 0
    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex, out.open("a", encoding="utf-8") as f:
        for res in ex.map(one, todo):
            with lock:
                f.write(json.dumps(res) + "\n")
                f.flush()
                spent += res["cost_usd"] or 0.0
                n_err += bool(res["error"])
    log(f"judge done: {len(todo) - n_err} answered, {n_err} errors (rerun to retry), spent ${spent:.2f} -> {out}")
    return {"todo": len(todo), "est_cost": est, "sent": len(todo), "errors": n_err, "spent": spent}
