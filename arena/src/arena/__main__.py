"""arena CLI.

    python -m arena run sweeps/smoke.yaml [--api mock|local|shared|URL] [--dry-run] [--approve-cost N]
    python -m arena models [--check]
    python -m arena play --model claude-haiku-5-5 --game <game_id> [--api ...] [--effort low]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .frames import _repo_root


def load_dotenv() -> None:
    p = _repo_root() / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def use_os_trust_store() -> None:
    """Verify TLS with the OS certificate store (Windows/macOS) instead of certifi. Venue networks,
    antivirus TLS inspection and some tunnels otherwise fail with CERTIFICATE_VERIFY_FAILED in
    httpx / anthropic / openai while curl works. Verification stays on."""
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass


def main(argv=None):
    use_os_trust_store()
    load_dotenv()
    ap = argparse.ArgumentParser(prog="arena")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("sweep")
    r.add_argument("--api", default="shared")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--approve-cost", type=float)
    r.add_argument("--out", default=str(Path.home() / "junction-data" / "arena"))
    r.add_argument("--also-done", action="append", default=[], help="URL of a previous shared server whose finished "
                   "runs count as done (not yet merged into --api)")
    m = sub.add_parser("models")
    m.add_argument("--check", action="store_true", help="query live /models endpoints for each provider")
    p = sub.add_parser("play")
    p.add_argument("--model", required=True)
    p.add_argument("--game", required=True)
    p.add_argument("--api", default="local")
    p.add_argument("--effort")
    d = sub.add_parser("dataset", help="build SFT data (A3-09) from train games")
    d.add_argument("--collection", help="train collection name/path (never eval)")
    d.add_argument("--seeds", help="spec seeds instead of a collection, e.g. 0-199")
    d.add_argument("--levels", type=int, default=6)
    d.add_argument("--recover", type=float, default=2, help="recover-from-mistake trajectories per game (fractional = probability)")
    d.add_argument("--gameover", type=float, default=1, help="blow-a-level-then-RESET trajectories per game (fractional = probability)")
    d.add_argument("--out", required=True)
    h = sub.add_parser("harbor-export", help="export games as Harbor tasks (AfterQuery judging harness)")
    h.add_argument("--collection", required=True)
    h.add_argument("--out", required=True)
    h.add_argument("--first", type=int)
    h.add_argument("--agent-timeout", type=int, default=3600)
    h.add_argument("--extra-ca", help="LOCAL ONLY: PEM root CA to trust inside task containers (antivirus TLS scanning)")
    h.add_argument("--vendor", help="LOCAL ONLY: Linux py3.12 site-packages dir for the sidecar (built with uv --target)")
    j = sub.add_parser("judge", help="judge-LLM calls for failure explanations (prompts jsonl from A5's analysis)")
    j.add_argument("--in", dest="inp", required=True, help="jsonl: {id, prompt, system?, max_tokens?} per line")
    j.add_argument("--out", required=True, help="jsonl replies (appended; rerun resumes)")
    j.add_argument("--model", default="gemini-pro")
    j.add_argument("--effort")
    j.add_argument("--max-tokens", type=int, default=8000, help="includes hidden thinking tokens on Gemini")
    j.add_argument("--concurrency", type=int, default=4)
    j.add_argument("--dry-run", action="store_true")
    j.add_argument("--approve-cost", type=float)
    sub.add_parser("judge-one", help="one judge call: JSON {system, prompt, max_tokens} on stdin -> JSON reply on stdout")
    a = ap.parse_args(argv)

    if a.cmd == "judge-one":
        from .judge import judge_one_stdin
        judge_one_stdin()
        return

    if a.cmd == "judge":
        from .judge import run as judge_run
        from .runner import spend_cap
        judge_run(Path(a.inp), Path(a.out), model_id=a.model, effort=a.effort, max_tokens=a.max_tokens,
                  concurrency=a.concurrency, dry_run=a.dry_run, approve_cost=a.approve_cost, cap=spend_cap())
        return

    if a.cmd == "harbor-export":
        from .harbor.export import export
        export(a.collection, Path(a.out), first=a.first, agent_timeout=a.agent_timeout,
               extra_ca=Path(a.extra_ca) if a.extra_ca else None, vendor=Path(a.vendor) if a.vendor else None)
        return

    if a.cmd == "dataset":
        from .dataset import build, games_from
        from .engine_adapter import load_engine
        eng, name = load_engine()
        print(f"engine: {name}")
        seeds = None
        if a.seeds:
            lo, _, hi = a.seeds.partition("-")
            seeds = list(range(int(lo), int(hi or lo) + 1))
        build(games_from(eng, a.collection, seeds, a.levels), Path(a.out).expanduser(), n_recover=a.recover, n_gameover=a.gameover)
        return

    if a.cmd == "run":
        from .runner import execute, load_sweep
        execute(load_sweep(a.sweep), api=a.api, dry_run=a.dry_run, approve_cost=a.approve_cost, out_dir=Path(a.out),
                also_done=a.also_done)
    elif a.cmd == "models":
        from .registry import load_models, usable
        models = load_models()
        for mm in models.values():
            flag = "ok " if usable(mm) else "TBD"
            print(f"[{flag}] {mm['id']:<22} {mm['provider']:<12} {str(mm['api_model']):<24} "
                  f"in ${mm['price_in']}/M out ${mm['price_out']}/M  {mm['input_modes']}")
        if a.check:
            from .providers.openai_compat import ENDPOINTS, list_remote_models
            for prov in sorted({mm["provider"] for mm in models.values()} & set(ENDPOINTS)):
                key = ENDPOINTS[prov][1]
                if not os.environ.get(key):
                    print(f"{prov}: no {key} in env, skipped")
                    continue
                try:
                    ids = list_remote_models(prov)
                    print(f"{prov}: {len(ids)} models, e.g. {', '.join(sorted(ids)[:15])}")
                except Exception as e:
                    print(f"{prov}: {type(e).__name__}: {e}")
    elif a.cmd == "play":
        from .agent_loop import Budgets, play_model
        from .client import make_client
        from .providers import get_provider
        from .registry import load_models
        mm = load_models()[a.model]
        res = play_model(make_client(a.api), a.game, get_provider(mm), mm, effort=a.effort or mm.get("default_effort"),
                         run_key=None, budgets=Budgets())
        print(res)


if __name__ == "__main__":
    main()
