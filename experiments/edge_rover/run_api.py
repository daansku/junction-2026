"""Rover v2 with API models (same prompt, same parser, same missions as run_eval2.py), one thread per mission.

    python run_api.py --model gemini-flash --effort high --seeds 5000-5029 --controls hidden,fixed --outdir results
Uses the arena model registry (arena/models.yaml) and the repo .env for keys (never printed).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "arena" / "src")]

from mission2 import Rover
from run_eval2 import SYSTEM, parse, seeds_of


def load_env() -> None:
    import os
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--seeds", default="5000-5029")
    ap.add_argument("--controls", default="hidden,fixed")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--workers", type=int, default=30)
    a = ap.parse_args()
    load_env()
    import yaml
    from arena.providers.openai_compat import make_client
    m = next(x for x in yaml.safe_load((ROOT / "arena" / "models.yaml").read_text(encoding="utf-8")) if x["id"] == a.model)
    client = make_client(m["provider"], m.get("base_url"), m.get("api_key_env")).with_options(timeout=300, max_retries=8)
    name = f"{a.model}@{a.effort}"
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.progress").write_text("")

    def episode(seed: int, controls: str) -> dict:
        e = Rover.create(seed, controls)
        notes, last, invalid, turns, errors = "", "", 0, 0, 0
        while not e.done and turns < e.energy_max + 10:
            msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": e.prompt(notes, last)}]
            try:
                r = client.chat.completions.create(model=m["api_model"], messages=msgs, reasoning_effort=a.effort,
                                                   max_tokens=16384)
                text = (r.choices[0].message.content or "") if r.choices and r.choices[0].message else ""
            except Exception as ex:  # count and retry the turn a few times; then it is an invalid turn
                errors += 1
                if errors > 20:
                    break
                time.sleep(5)
                continue
            turns += 1
            act, new = parse(text)
            if act is None:
                invalid += 1
                last = "INVALID REPLY: answer with the JSON and one of ACTION1-ACTION4"
                notes = new or notes
                continue
            notes, last = new, e.act(act)
        with open(out / f"{name}.progress", "a") as f:
            f.write(f"{controls} {seed} {int(e.success)}\n")
        return {"model": name, "controls": controls, "seed": seed, "success": e.success, "found": e.found,
                "steps": e.steps, "bumps": e.bumps, "energy_left": e.energy, "energy_max": e.energy_max,
                "one_way": e.path_len, "invalid": invalid, "turns": turns, "api_errors": errors,
                "mapping": e.mapping, "history": e.history}

    jobs = [(s, c) for c in a.controls.split(",") for s in seeds_of(a.seeds)]
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda j: episode(*j), jobs))
    for c in a.controls.split(","):
        rs = [r for r in rows if r["controls"] == c]
        (out / f"{name}-{c}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8")
        print(json.dumps({"model": name, "controls": c, "n": len(rs), "success": sum(r["success"] for r in rs),
                          "found": sum(r["found"] for r in rs), "invalid": sum(r["invalid"] for r in rs),
                          "api_errors": sum(r["api_errors"] for r in rs), "wall_s": round(time.time() - t0)}),
              flush=True)


if __name__ == "__main__":
    main()
