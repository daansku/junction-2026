# Running our games in Harbor (the AfterQuery judging harness)

The judges rerun everything with **Harbor + OpenCode over MCP**: a reference run, three agent runs,
a do-nothing baseline and a stop-early baseline, then spend 15 minutes hunting reward exploits
(docs/CHALLENGE.md). This folder turns each game into a Harbor task they can run as-is.

```bash
python -m arena harbor-export --collection eval-v1 --out harbor/eval-v1
harbor run -p harbor/eval-v1 -a oracle                          # reference run: optimal play -> reward 1.0
harbor run -p harbor/eval-v1 -a nop                             # do-nothing baseline -> 0
harbor run -p harbor/eval-v1 -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1   # stop-early baseline: level 1 only -> 1/6
harbor run -p harbor/eval-v1 -a opencode -m <provider/model>    # frontier agent (repeat x3)
```

## What a task contains
| file | role |
|---|---|
| `task.toml` | schema 1.1; `game` MCP server (`streamable-http`, `http://game:8000/mcp`); **separate** verifier; `/evidence/score.json` collected from the `game` service as an artifact |
| `instruction.md` | tools, actions, "find the goal yourself", scoring; no rules, no colours, no numbers |
| `environment/Dockerfile` | the agent's container: plain ubuntu, **no game code** |
| `environment/docker-compose.yaml` | adds the `game` sidecar (built from `environment/game/`) |
| `environment/game/` | engine + `arena.harbor.sidecar` + a one-game collection |
| `tests/test.sh` | separate verifier: reads the collected `/evidence/score.json` -> `/logs/verifier/reward.json` + `reward.txt` |
| `solution/solve.sh` | oracle: replays the optimal path through the MCP tools |

## Reward
Per PLAN.md §4.6 (ARC-AGI-3 style): mean over levels of `min(1, optimal_moves / actions_on_level)` for solved
levels, 0 for unsolved. Every move and RESET on a level counts. In [0, 1]; only optimal play reaches 1.

## Exploit surface (what judges can poke at)
- The agent reaches the sidecar over the network, so the sidecar exposes **only** MCP `observe()` / `act()`
  plus `/healthz`. No game list, no restart-from-level-1, no truth, no optimal path, no score endpoint.
- Grading never touches the agent's container or network. The sidecar writes `/evidence/score.json` in its
  own container after every action; Harbor stops the agent container, collects that file as an artifact,
  and runs `tests/test.sh` in a **separate** verifier container. (An earlier design read a token-protected
  HTTP score endpoint from a shared verifier; `harbor lint` flagged the shared verifier, and an agent could
  have pointed `game` at a fake server via `/etc/hosts`. Fixed.) Missing evidence = reward 0.
- Invalid actions are rejected and not counted; actions after the win do nothing; a hard cap (3000) on total actions.
- Doing nothing = 0. Stopping early = credit only for levels actually solved, discounted by actions used.
- Claims in text are ignored: the reward comes from the sidecar's game state only.

## Verified (2026-11-14, on A1's `dev` collection)
- Unit tests: optimal = 1.0, nothing = 0, stop one move short = 0, one wasted RESET = exact partial credit,
  invalid input and post-win actions not counted, only two MCP tools, no `/score` route, evidence file tracks score.
- `harbor lint` (Harbor 0.26.0): clean. Harbor's `TaskConfig` parses the exported `task.toml`.
- Native run of an exported sidecar over real MCP streamable HTTP (token-endpoint version): the oracle client from
  `solve.sh` replayed 119 actions -> reward 1.0, 6/6 levels.
- **Not yet run:** the Docker build and a full `harbor run` (Docker Desktop was not running on this machine;
  Harbor CLI now installed on this machine).

## Oracle needs no downloads
`solution/solve.sh` embeds a ~60-line standard-library MCP client (`arena/harbor/mcp_mini.py`), so the reference
run works offline and behind TLS-inspecting proxies.

## Local machines with antivirus TLS scanning
Norton "Web/Mail Shield" (and similar) re-signs HTTPS with its own root, so downloads inside task containers fail
(`CERTIFICATE_VERIFY_FAILED`). `--extra-ca <pem>` bakes that root into the task containers for **local runs only**;
never hand such an export to judges. On ignacio's machine Norton also corrupts chunked downloads even when the
certificate is trusted (`InvalidChunkLength` from pip, on the host too). Workaround that needs no settings change:
build the sidecar's Linux dependencies on the host with uv (which copes) and pass them in:

    uv pip install --target vendor --python-platform x86_64-manylinux_2_17 --python-version 3.12 "mcp>=1.6,<2"
    python -m arena harbor-export --collection dev --out C:/hb-local --extra-ca norton-root.crt --vendor vendor

Both flags are local-only. Tasks for judges are exported without them.
