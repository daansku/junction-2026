"""Fetch A3's edge rover results for the rover scene into video/cache/rover/.

Reads video/rover.json (git ref, which mission to replay), pulls mission2.py and the results file with
`git show <ref>:experiments/edge_rover/...` (the experiment may live on a branch), rebuilds the mission map
from its seed and writes video/cache/rover/mission.json (walls, beacon, base, path, controls, notes).

Usage (from the repo root):  video/.venv/python.exe video/tools/fetch_rover.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
VIDEO = ROOT / "video"
OUT = VIDEO / "cache" / "rover"
EXP = "experiments/edge_rover"


def git_show(ref: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{ref}:{EXP}/{path}"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def main() -> None:
    cfg = json.loads((VIDEO / "rover.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mission2.py").write_text(git_show(cfg["git_ref"], "mission2.py"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("mission2", OUT / "mission2.py")
    m2 = importlib.util.module_from_spec(spec)
    sys.modules["mission2"] = m2          # dataclasses look the module up by name
    spec.loader.exec_module(m2)

    mc = cfg["mission"]
    rows = [json.loads(l) for l in git_show(cfg["git_ref"], mc["file"]).splitlines() if l.strip()]
    run = next(r for r in rows if r["seed"] == mc["seed"])
    rover = m2.Rover.create(run["seed"], run["controls"])
    path = [list(rover.pos)]
    for h in run["history"]:
        act = h.split(":")[0]
        rover.act(act)
        path.append(list(rover.pos))
    notes = []
    for rep in run.get("first_replies", []):
        mm = re.search(r'"notes"\s*:\s*"(.*?)"', rep, re.S)
        notes.append(mm.group(1) if mm else "")
    out = {
        "seed": run["seed"], "controls": run["controls"], "size": m2.SIZE, "base": list(m2.BASE),
        "walls": sorted(list(w) for w in rover.walls), "goal": list(rover.goal), "mapping": run["mapping"],
        "actions": [h.split(":")[0] for h in run["history"]], "events": run["history"], "path": path,
        "success": run["success"], "steps": run["steps"], "energy_max": run["energy_max"], "notes": notes,
    }
    assert rover.success == run["success"], "replay does not match the recorded run"
    (OUT / "mission.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"seed {run['seed']}: {run['steps']} steps, success={run['success']}")


if __name__ == "__main__":
    main()
