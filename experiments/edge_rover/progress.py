"""Live progress for the rover v2 THINKING-ON eval (base vs think-games-h2 step-60), with direction metrics.

    python progress.py          # refreshes every 20 s, Ctrl+C to quit

good-move %  share of moves that brought the rover closer (true shortest path) to its current target
             (the beacon, then base). Random play: ~40%. Higher = heading the right way.
dist         mean true distance of live rovers to their current target (should fall).
"""
from __future__ import annotations

import json
import os
import subprocess
import time

KEY = os.path.expanduser("~/.ssh/junction_verda2")
RUNS = [  # label, host, workdir, name
    ("BASE Qwen3.5-9B (A100 gpu0)", "95.216.229.250", "/root/rover2", "base"),
    ("RL think-games-h2 s60 (H100)", "31.22.104.125", "/root/edge_rover", "think-h2-s60"),
]
W = 24
MAXSTEP = 55
RANDOM_GOOD = 40


def bar(frac: float) -> str:
    f = int(W * min(1.0, frac))
    return "[" + "#" * f + "-" * (W - f) + "]"


def fetch(host: str, wd: str, name: str) -> dict:
    cmd = (f"for c in hidden fixed; do echo \"== $c $(test -f {wd}/think/{name}-$c.jsonl && echo DONE)\"; "
           f"tail -n 40 {wd}/think/{name}-$c.metrics.jsonl 2>/dev/null; done; "
           f"echo \"== tb $(grep -c Traceback {wd}/think-{name}.log)\"")
    try:
        out = subprocess.run(["ssh", "-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", f"root@{host}", cmd],
                             capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return {}
    res, cur = {}, None
    for line in out.splitlines():
        if line.startswith("== "):
            p = line.split()
            cur = p[1]
            res[cur] = {"done": "DONE" in p, "rows": [], "tb": p[2] if cur == "tb" and len(p) > 2 else "0"}
        elif line.startswith("{") and cur:
            res[cur]["rows"].append(json.loads(line))
    return res


def spark(vals: list[float], lo: float = 0, hi: float = 100) -> str:
    ticks = " .:-=+*#%@"
    return "".join(ticks[min(9, max(0, int((v - lo) / (hi - lo) * 9.99)))] for v in vals)


def main() -> None:
    t0 = time.time()
    while True:
        lines = [f"Rover v2, thinking ON, 100 held-out missions   {time.strftime('%H:%M:%S')}   "
                 f"(watching {int(time.time() - t0)}s)",
                 f"good-move % = moves that got closer to the target (beacon, then base); random play ~{RANDOM_GOOD}%", ""]
        for label, host, wd, name in RUNS:
            r = fetch(host, wd, name)
            lines.append(label + ("   !! Traceback in log" if r.get("tb", {}).get("tb", "0") not in ("0", "") else ""))
            if not r:
                lines.append("    (ssh failed, retrying)")
                continue
            for c in ("hidden", "fixed"):
                x = r.get(c, {"rows": [], "done": False})
                if not x["rows"]:
                    lines.append(f"    {c:6s} {bar(0)} waiting (loading model / other condition first)")
                    continue
                m = x["rows"][-1]
                state = "DONE" if x["done"] else f"step {m['step']:2d}"
                lines.append(f"    {c:6s} {bar(1 if x['done'] else m['step'] / MAXSTEP)} {state:8s} live {m['live']:3d}/{m['n']}"
                             f"  found {m['found']:3d}  SUCCESS {m['success']:3d}")
                lines.append(f"           good-move {m['good_pct_cum']:5.1f}% overall (last step {m['good_pct']:5.1f}%)"
                             f"  bumps {m['bump_pct']:4.1f}%  dist {m['mean_dist']:.1f}"
                             f"  trend |{spark([y['good_pct'] for y in x['rows']])}|")
            lines.append("")
        lines += ["Thinking OFF (final, 150 seeds): base 8 hidden / 17 fixed; GRPO-1 0 / 2; GRPO-2 0 / 3",
                  "Gemini (30 seeds): Argon 30/30 both; Flash 29/30 hidden, 28/30 fixed"]
        os.system("cls" if os.name == "nt" else "clear")
        print("\n".join(lines), flush=True)
        time.sleep(20)


if __name__ == "__main__":
    main()
