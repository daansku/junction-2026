# Judging path: Harbor + OpenCode over MCP

PLAN.md assigns none of this. A human decided on Sat 14.11 03:21: **the team does the missing pieces now, with the owners below.**
`DECISIONS.md` should get a line pointing here.

## What judges do (docs/CHALLENGE.md)
They rerun with their standard harness, **Harbor running the OpenCode agent over MCP**:
a reference run, 3 agent runs, a do-nothing baseline and a stop-early baseline.
Then they spend 15 minutes hunting reward exploits. They must be able to run the eval from the README with one command.

## Decision
- **Official judging path = A3's Harbor export** (`arena/HARBOR.md`, `python -m arena harbor-export`).
  The game runs in a sidecar exposing only MCP `observe`/`act`. Its score is written inside the sidecar and graded by a separate verifier container.
- **No second judging path.** A2 does not build a fixed-game MCP mode or a score endpoint for judging. `python -m server mcp` (A2-06) stays for the demo and dev, and is not what judges run.
- Docs must send judges to the Harbor commands, not to `python -m server mcp`.

## Owners and checklist
| # | Task | Owner | Status |
|---|---|---|---|
| 1 | Harbor task export: sidecar, verifier, oracle (reference), nop (do-nothing) | A3 | done (`harbor lint` clean, oracle 1.0 natively) |
| 2 | **Stop-early baseline**: `-a oracle --ae ORACLE_STOP_AFTER_LEVELS=<n>` (oracle replays only the first n levels) | A4 | done |
| 3 | **Docker build + full `harbor run`** with oracle / nop / stop-early on `dev` (needs Docker: A4's machine has it) | A4 | done (see Results) |
| 4 | **OpenCode agent run** through Harbor, using the organisers' Nemotron opencode config (`NVIDIA_VERDA_INFERENCE_KEY`, see `coordination/KEYS.md`) | A4 | running |
| 5 | Export the frozen `eval-v1` after the 11:00 freeze and rerun oracle once | A3 | after 11:00 |
| 6 | README one-command eval + fix SUBMISSION / QA_PREP / DEMO_SCRIPT / PITCH to use the Harbor commands | A5 | todo |
| 7 | Reward integrity check: do-nothing = 0, stop-early earns only the solved levels, oracle = 1.0, reported in the deck | A5 (numbers from A4's runs) | todo |

Update the Status column when you finish a row.
Results of the runs go under "Results" below, with the exact commands.

## Results
Sat 14.11 03:2x, A4's machine: Docker 29.8.1, Harbor 0.26.0 (`uv tool install harbor==0.26.0`).
Task: `dev` game `gridworld-s1000-d1-l6-9b1065f8` (engine 0.5.0, 6 levels, optimal 92 actions).
Exported with `python -m arena harbor-export --collection dev --out <dir> --first 2`; `harbor lint <task dir>` is clean.
Full Docker builds; agent and game run as separate containers; the verifier runs in its own container.

| Run | Command | Actions | Levels | Reward |
|---|---|---|---|---|
| reference (oracle) | `harbor run -p <task> -a oracle` | 92 | 6/6 | **1.000** |
| do-nothing | `harbor run -p <task> -a nop` | 0 | 0/6 | **0.000** |
| stop-early after level 1 | `harbor run -p <task> -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1` | 13 | 1/6 | **0.167** |
| stop-early after level 3 | `... --ae ORACLE_STOP_AFTER_LEVELS=3` | 45 | 3/6 | **0.500** |

Each oracle run takes about 70 s, most of it Docker build and uv install.
