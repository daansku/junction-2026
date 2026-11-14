# Running our games in Harbor (the AfterQuery judging harness)

The judges rerun everything with **Harbor + OpenCode over MCP**: a reference run, three agent runs,
a do-nothing baseline and a stop-early baseline, then spend 15 minutes hunting reward exploits
(docs/CHALLENGE.md). This folder turns each game into a Harbor task they can run as-is.

```bash
python -m arena harbor-export --collection eval-v1 --out harbor/eval-v1
harbor run -p harbor/eval-v1 -a oracle                          # reference run: optimal play -> reward 1.0
harbor run -p harbor/eval-v1 -a nop                             # do-nothing baseline -> 0
harbor run -p harbor/eval-v1 -a opencode -m <provider/model>    # frontier agent (repeat x3)
```

## What a task contains
| file | role |
|---|---|
| `task.toml` | schema 1.1; declares the `game` MCP server (`streamable-http`, `http://game:8000/mcp`) |
| `instruction.md` | tools, actions, "find the goal yourself", scoring; no rules, no colours, no numbers |
| `environment/Dockerfile` | the agent's container: plain ubuntu, **no game code** |
| `environment/docker-compose.yaml` | adds the `game` sidecar (built from `environment/game/`) |
| `environment/game/` | engine + `arena.harbor.sidecar` + a one-game collection |
| `tests/test.sh` | verifier: `GET /score?token=...` -> `/logs/verifier/reward.json` + `reward.txt` |
| `solution/solve.sh` | oracle: replays the optimal path through the MCP tools |

## Reward
Per PLAN.md §4.6 (ARC-AGI-3 style): mean over levels of `min(1, optimal_moves / actions_on_level)` for solved
levels, 0 for unsolved. Every move and RESET on a level counts. In [0, 1]; only optimal play reaches 1.

## Exploit surface (what judges can poke at)
- The agent reaches the sidecar over the network, so the sidecar exposes **only** MCP `observe()` / `act()`
  plus `/healthz`. No game list, no restart-from-level-1, no truth, no optimal path, no rule names.
- `/score` needs a random per-task token that exists only in the sidecar env and `tests/test.sh`; Harbor
  uploads `tests/` after the agent finishes. Wrong or missing token -> 403.
- Invalid actions are rejected and not counted; actions after the win do nothing; a hard cap (3000) on total actions.
- Doing nothing = 0. Stopping early = credit only for levels actually solved, discounted by actions used.
- Claims in text are ignored: the reward comes from the sidecar's game state only.

## Verified (2026-11-14, on A1's `dev` collection)
- Unit tests: optimal = 1.0, nothing = 0, stop one move short = 0, one wasted RESET = exact partial credit,
  invalid input and post-win actions not counted, only two MCP tools, `/score` 403 without the token.
- Native run of an exported sidecar over real MCP streamable HTTP: the oracle client from `solve.sh` replayed
  119 actions -> reward 1.0, 6/6 levels; the verifier script wrote `reward.json`.
- **Not yet run:** the Docker build and a full `harbor run` (Docker Desktop was not running on this machine;
  Harbor CLI not installed here).
