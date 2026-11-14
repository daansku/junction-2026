"""Summarise Harbor smoke runs: one row per model (actions, levels, reward, error, OpenCode errors, tool calls).

    python3 arena/harbor_smoke_report.py <OUT_DIR>      # OUT_DIR from arena/harbor_models_smoke.sh

A model "works" when the agent made game actions (actions > 0). AgentTimeoutError is expected: the smoke cap
cuts every run short, so the rewards here are not results.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def trial_rows(out: Path):
    for res in sorted(out.glob("*/*/*/result.json")):
        d = json.loads(res.read_text())
        trial = res.parent
        model = (d.get("config", {}).get("agent", {}) or {}).get("model_name") or trial.parts[-3]
        rw = (d.get("verifier_result") or {}).get("rewards") or {}
        exc = (d.get("exception_info") or {}).get("exception_type") or ""
        oc = trial / "agent" / "opencode.txt"
        tool_calls, errors = {}, []
        if oc.exists():
            for line in oc.read_text(errors="replace").splitlines():
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "tool_use":
                    name = (ev.get("part") or {}).get("tool", "?")
                    tool_calls[name] = tool_calls.get(name, 0) + 1
                elif ev.get("type") == "error":
                    err = ev.get("error") or ev
                    errors.append(json.dumps(err)[:160])
        yield {
            "model": model,
            "actions": rw.get("actions"),
            "levels": f"{rw.get('levels_solved', '-')}/{rw.get('levels_total', '-')}",
            "reward": rw.get("reward"),
            "exception": exc,
            "tools": tool_calls,
            "errors": errors[:2],
            "works": bool(rw.get("actions")),
        }


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/harbor-models-smoke")
    rows = list(trial_rows(out))
    if not rows:
        print(f"no trials under {out}")
        return
    print(f"| model | works | actions | levels | reward (capped run) | exception | tool calls | OpenCode errors |")
    print("|---|---|---:|---|---:|---|---|---|")
    for r in rows:
        tools = ", ".join(f"{k} {v}" for k, v in sorted(r["tools"].items())) or "-"
        print(f"| `{r['model']}` | {'yes' if r['works'] else '**no**'} | {r['actions']} | {r['levels']} | "
              f"{r['reward']} | {r['exception'] or '-'} | {tools} | {'; '.join(r['errors']) or '-'} |")


if __name__ == "__main__":
    main()
