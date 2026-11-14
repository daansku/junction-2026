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
| 2 | **Stop-early baseline** as a Harbor agent | A4 | in progress |
| 3 | **Docker build + full `harbor run`** with oracle / nop / stop-early on `dev` (needs Docker: A4's machine has it) | A4 | in progress |
| 4 | **OpenCode agent run** through Harbor, using the organisers' Nemotron opencode config (`NVIDIA_VERDA_INFERENCE_KEY`, see `coordination/KEYS.md`) | A4 | todo |
| 5 | Export the frozen `eval-v1` after the 11:00 freeze and rerun oracle once | A3 | after 11:00 |
| 6 | README one-command eval + fix SUBMISSION / QA_PREP / DEMO_SCRIPT / PITCH to use the Harbor commands | A5 | todo |
| 7 | Reward integrity check: do-nothing = 0, stop-early earns only the solved levels, oracle = 1.0, reported in the deck | A5 (numbers from A4's runs) | todo |

Update the Status column when you finish a row.
Results of the runs go under "Results" below, with the exact commands.

## Results
_(A4 fills this in from the real `harbor run`s.)_
