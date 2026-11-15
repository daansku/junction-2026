"""Live progress for the episodic RL (expert iteration) pipeline on Qwen3.5-4B: rollouts -> training -> rover eval.

    python progress_rl.py        # refreshes every 20 s, Ctrl+C to quit
"""
from __future__ import annotations

import json
import os
import subprocess
import time

KEY = os.path.expanduser("~/.ssh/junction_verda2")
H100, A100, B200 = "31.22.104.125", "95.216.229.250", "95.133.252.154"
MAX_WALL = 780
MAX_STEPS = 24  # cap: 2 x 10 + 4
W = 28


def bar(frac: float) -> str:
    f = int(W * max(0.0, min(1.0, frac)))
    return "[" + "#" * f + "-" * (W - f) + "]"


def ssh(host: str, cmd: str) -> str:
    key = os.path.expanduser("~/.ssh/a3_b200") if host == B200 else KEY
    try:
        return subprocess.run(["ssh", "-i", key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", f"root@{host}", cmd],
                              capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return ""


def ro_line(host: str, log: str, label: str) -> str:
    out = ssh(host, f"grep '^{{' {log} | tail -1; grep -o 'wrote.*' {log}")
    rows = [l for l in out.splitlines() if l.startswith("{")]
    if "wrote" in out:
        return f"   {label:5s} {bar(1)} DONE  {out.split('wrote', 1)[1].splitlines()[0].strip()}"
    if rows:
        r = json.loads(rows[-1])
        frac = max(r["t"] / MAX_WALL, r["step"] / MAX_STEPS)
        return (f"   {label:5s} {bar(frac)} step {r['step']:2d}  live {r['live']:3d}/{r['episodes']}  SOLVED {r['solved']:3d}"
                f"  ({r['t'] // 60} min)")
    return f"   {label:5s} {bar(0)} loading model"


def rover_line(host: str, path: str, done_path: str) -> str:
    out = ssh(host, f"tail -n1 {path} 2>/dev/null; test -f {done_path} && echo DONE")
    rows = [l for l in out.splitlines() if l.startswith("{")]
    if not rows:
        return "   waiting"
    r = json.loads(rows[-1])
    state = "DONE   " if "DONE" in out else f"step {r['step']:2d}"
    return (f"   {bar(1 if 'DONE' in out else r['step'] / 55)} {state}  live {r['live']:3d}/{r['n']}  found {r['found']:3d}"
            f"  SUCCESS {r['success']:3d}  good-move {r['good_pct_cum']}% (random ~40%)")


def main() -> None:
    while True:
        lines = [f"Episodic RL on our games -> rover transfer, Qwen3.5-4B   {time.strftime('%H:%M:%S')}", "",
                 "1) ROLLOUTS  ROUND 3: round-2 model plays 320 FRESH levels (10 optimal moves), 2 shots each (640 episodes)"]
        lines.append(ro_line(B200, "/root/a3rl/ro-b200.log", "B200"))
        tr = ssh(B200, "cat /root/a3rl/build3.log 2>/dev/null | tail -1; "
                       "tail -c 300 /root/a3rl/train3.log 2>/dev/null | tr '\r' '\n' | grep -v '^$' | tail -1").splitlines()
        lines += ["", "2) TRAIN (B200)  LoRA on the 4B's own solved episodes, then merge"]
        lines += ["   " + l[:120] for l in tr] if tr else ["   waiting for rollouts"]
        lines += ["", "3) ROVER-LITE (7x7, beacon 3-6 away), hidden controls, same 100 missions, thinking <=512 tokens",
                  "   4B BASE, JSON repair on (H100):"]
        lines.append(rover_line(H100, "/root/edge_rover/think/base4b-lite-v2-hidden.metrics.jsonl",
                                "/root/edge_rover/think/base4b-lite-v2-hidden.jsonl"))
        lines.append("   4B after ROUND 3, JSON repair on (B200)   [base 41, R1 50, R2 54]:")
        lines.append(rover_line(B200, "/root/a3rl/think/rft4b-r3-lite-hidden.metrics.jsonl",
                                "/root/a3rl/think/rft4b-r3-lite-hidden.jsonl"))
        os.system("cls" if os.name == "nt" else "clear")
        print("\n".join(lines), flush=True)
        time.sleep(20)


if __name__ == "__main__":
    main()
