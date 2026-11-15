"""Summarise judge runs (arena/judge.sh output folders) as one Markdown table per folder.

    python3 arena/judge_report.py harbor/run-logs/<run> [<run> ...]

One row per trial: reward, levels, actions, agent minutes, how the attempt ended. "Ended" reads the trial's exception
and the OpenCode event log: `stop` = the agent chose to stop; `AgentTimeoutError` = the 60-min cap ended it (the
reward still counts what was played); `NonZeroAgentExitCodeError` + the OpenCode error = the agent harness crashed.
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path


def _minutes(a: dict) -> str:
    try:
        s = datetime.fromisoformat(a["started_at"].replace("Z", "+00:00"))
        f = datetime.fromisoformat(a["finished_at"].replace("Z", "+00:00"))
        return f"{(f - s).total_seconds() / 60:.0f}"
    except (KeyError, TypeError, ValueError):
        return "-"


def _ending(trial: Path, exc: str | None) -> str:
    oc = trial / "agent" / "opencode.txt"
    last_finish, err = None, None
    if oc.exists():
        for line in oc.read_text(errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "step_finish":
                last_finish = (e.get("part") or {}).get("reason")
            elif e.get("type") == "error" and err is None:
                d = e.get("error") or {}
                msg = " ".join(str((d.get("data") or {}).get("message", "")).replace("|", "/").split())
                if "ending with a model turn" in msg:
                    msg = "Requests ending with a model turn are not supported (HTTP 400)"
                err = f'{d.get("name")}: {msg}'[:120]
    if exc == "AgentTimeoutError":
        return "agent time cap (AgentTimeoutError)"
    if exc:
        return f"agent harness crashed ({exc}; {err})" if err else exc
    return "agent stopped by itself" if last_finish == "stop" else (last_finish or "finished")


def report(run: Path) -> str:
    out = [f"### `{run.name}`", "", "| run | attempt | reward | levels | actions | agent min | ended |",
           "|---|---|---:|---|---:|---:|---|"]
    for tag in sorted(p for p in run.iterdir() if p.is_dir()):
        rewards = []
        for res in sorted(tag.glob("*/*/result.json")):
            d = json.loads(res.read_text())
            rw = (d.get("verifier_result") or {}).get("rewards") or {}
            exc = (d.get("exception_info") or {}).get("exception_type")
            r = float(rw.get("reward", 0.0))
            rewards.append(r)
            out.append(f"| {tag.name} | `{res.parent.name.split('__')[-1]}` | {r:.3f} | "
                       f"{rw.get('levels_solved', 0)}/{rw.get('levels_total', '?')} | {rw.get('actions', 0)} | "
                       f"{_minutes(d.get('agent_execution') or {})} | {_ending(res.parent, exc)} |")
        if len(rewards) > 1:
            out.append(f"| {tag.name} | **mean of {len(rewards)}** | **{statistics.fmean(rewards):.3f}** | | | | |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print("\n".join(report(Path(p)) for p in sys.argv[1:]))
