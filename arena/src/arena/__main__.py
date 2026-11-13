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


def main(argv=None):
    load_dotenv()
    ap = argparse.ArgumentParser(prog="arena")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("sweep")
    r.add_argument("--api", default="shared")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--approve-cost", type=float)
    r.add_argument("--out", default=str(Path.home() / "junction-data" / "arena"))
    m = sub.add_parser("models")
    m.add_argument("--check", action="store_true", help="query live /models endpoints for each provider")
    p = sub.add_parser("play")
    p.add_argument("--model", required=True)
    p.add_argument("--game", required=True)
    p.add_argument("--api", default="local")
    p.add_argument("--effort")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        from .runner import execute, load_sweep
        execute(load_sweep(a.sweep), api=a.api, dry_run=a.dry_run, approve_cost=a.approve_cost, out_dir=Path(a.out))
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
