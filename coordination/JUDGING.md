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
| 4 | **OpenCode agent run** through Harbor, using the organisers' Nemotron opencode config (`NVIDIA_VERDA_INFERENCE_KEY`, see `coordination/KEYS.md`) | A4 | done once (see Results); 3 attempts in OVERNIGHT.md |
| 5 | Export the frozen `eval-v1` after the 11:00 freeze and rerun oracle once | A3 | done 13:25: `harbor/eval-v1/` (30 tasks, engine 0.6.0, lint clean); Docker oracle 1.0 / nop 0.0 / stop-early 0.167 (Results) |
| 6 | README one-command eval + fix SUBMISSION / QA_PREP / DEMO_SCRIPT / PITCH to use the Harbor commands | A5 | done (`README.md`, `docs/{SUBMISSION,QA_PREP,DEMO_SCRIPT,PITCH}.md`) |
| 7 | Reward integrity check: do-nothing = 0, stop-early earns only the solved levels, oracle = 1.0, reported in the deck | A5 (numbers from A4's runs) | done (`docs/deck/SLIDES.md`, `docs/deck/index.html`) |
| 8 | **Red-team the reward** from the agent's seat (custom Harbor agent inside the agent container): forged evidence, hidden files, side routes, malformed actions, sessions, races, spam | A4 | done Sat 14:55: every attack 0.0 (Results → Red team) |
| 9 | **Judge simulation:** fresh clone, follow `README.md` literally, oracle + nop on frozen `eval-v1` | A4 | done Sat 14:40: oracle 1.0 / nop 0.0 after `make setup`; README setup order + committed `harbor/eval-v1` command fixed by A5 |

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

**Independent reproduction (A3, 03:30, ignacio's machine, Docker 29.9.2, Harbor 0.26.0), same game:** oracle 1.000
(6/6, 92 actions), nop 0.000. That machine runs Norton TLS scanning, which breaks pip inside containers, so it used a
local-only export (`--extra-ca`, `--vendor`; task logic identical). Since then `solve.sh` uses a standard-library MCP
client, so the oracle/stop-early runs no longer download uv or mcp inside the agent container.

### OpenCode + Nemotron 3.5 Super VL through Harbor (judges' path)
Config: `arena/opencode-nemotron.json` (organisers' config, rewritten in OpenCode's `provider` schema).
```bash
set -a; . ./.env; set +a      # host env must hold NVIDIA_VERDA_INFERENCE_KEY
harbor run -p <task> -a opencode -m verda-nemotron/nemotron-3.5-super-vl \
  --ak "opencode_config=$(python3 -c 'import json;print(json.dumps(json.load(open("arena/opencode-nemotron.json"))))')" \
  --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' \
  --agent-timeout-multiplier 0.25        # 15 min cap for testing; judges use the task default (2 h since Sun 05:00; was 60 min)
```
- The `${...}` template is required: without `--ae`, the key never reaches the agent container, and Verda answers 404. Harbor stores only the template in the job's `config.json`, not the key.
- `--ak config=<file>` is rejected by Harbor 0.26 for opencode ("does not support config"). Use `opencode_config`.

| Run | Actions | Invalid | Levels | Reward | Note |
|---|---|---|---|---|---|
| OpenCode + Nemotron, attempt 1 | 94 | 2 | 2/6 | **0.113** | hit the 15-min test cap (AgentTimeoutError); level 1 at 2× optimal, level 2 at 5.7× |
| OpenCode + Nemotron, k=3 run (08:02), attempt A | 155 | 3 | 1/6 | **0.020** | 30-min cap (`--agent-timeout-multiplier 0.5`), AgentTimeoutError |
| OpenCode + Nemotron, k=3 run (08:02), attempt B | 135 | 2 | 1/6 | **0.094** | 30-min cap, AgentTimeoutError |
| OpenCode + Nemotron, k=3 run, attempt C (rerun 08:38) | 227 | 3 | 1/6 | **0.087** | first try hit AgentSetupTimeoutError (OpenCode install > 360 s with 3 setups in parallel); rerun with `-k 1 --agent-setup-timeout-multiplier 2`, 30-min cap, AgentTimeoutError |

`-k 3 -n 3` = 3 attempts in parallel. With `-n 3`, give setup more time (`--agent-setup-timeout-multiplier 2`), or use `-n 1`.
Rubric set (3 agent runs, 30-min cap): 0.020, 0.094, 0.087, **mean 0.067**. With the earlier 15-min attempt (0.113), 4 runs average 0.079. Reference: 1.000, do-nothing: 0.000.

The reference run scores 1.000 on the same task. The gap shows on the judges' own harness.

**Frozen `eval-v1` (A3, 13:25, ignacio's machine, Docker 29.9.2, Harbor 0.26.0).** The judges' package is committed at
`harbor/eval-v1/` (30 tasks, one per game, engine 0.6.0, `harbor lint` clean, no local-only CA/vendor). Game 1
(`gridworld-s900000-d1-l6-33a57ce4`), run from a local copy that only adds the antivirus CA:

| Run | Command | Reward | Levels | Actions | Errors |
|---|---|---|---|---|---|
| reference (oracle) | `harbor run -p harbor/eval-v1 -a oracle` | **1.000** | 6/6 | 86 | 0 |
| do-nothing | `harbor run -p harbor/eval-v1 -a nop` | **0.000** | 0/6 | 0 | 0 |
| stop-early | `harbor run -p harbor/eval-v1 -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1` | **0.167** | 1/6 | 11 | 0 |

On Windows, `harbor run` exits 1 after writing results (`OPENSSL_Uplink: no OPENSSL_Applink`, a teardown crash); results and `n_errors: 0` are unaffected. Regenerate with `python -m arena harbor-export --collection eval-v1 --out harbor/eval-v1` (on Windows export to a short path such as `C:/hb` first: the repo path can exceed 260 characters).

**`eval-v2` (A3, 14:00, same machine).** Judges' package at `harbor/eval-v2/` (30 tasks x 8 levels, difficulty 4, 3 unseen rules per game; `harbor lint` clean, no local-only parts). Game 1 (`gridworld-s910000-d4-l8-f71ee29e`):

| Run | Reward | Levels | Actions | Errors |
|---|---|---|---|---|
| reference (oracle) | **1.000** | 8/8 | 187 | 0 |
| do-nothing | **0.000** | 0/8 | 0 | 0 |
| stop-early (`ORACLE_STOP_AFTER_LEVELS=1`) | **0.125** | 1/8 | 31 | 0 |

### Red team: trying to beat the reward from the agent's seat (A4, Sat 14:40-14:55)
Task `harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4` (solution folder removed from the copy), Docker + Harbor 0.26.0.
A custom Harbor agent (`coordination/redteam/redteam_agent.py`) runs `coordination/redteam/attack.py` **inside the agent
container**, the exact seat of a real agent: same filesystem, same network, same MCP endpoint.

| # | Attack | What happened | Reward |
|---|---|---|---|
| 1 | **Forge the score:** write `{"reward": 1.0, "won": true, ...}` to `/evidence/score.json`, `/logs/artifacts/evidence/score.json`, `/logs/artifacts/score.json`, and `1.0` to `/logs/verifier/reward.txt` / `reward.json`, play nothing | Writes succeed in the agent container, but the verifier reads the score Harbor collects from the **game** container (`[[artifacts]] service = "game"`) in a separate verifier container, and overwrites `reward.*` | **0.0** |
| 2 | **Find the answer on disk / in env:** `find /` for `solve.sh`, `collection.json`, `score.json`, `task.toml`, `test.sh`, `sidecar.py`; env vars | nothing found; env holds only `HOME PATH PWD ...` (no game id, no keys) | 0.0 |
| 3 | **Side routes on the game server:** `/`, `/docs`, `/openapi.json`, `/score`, `/truth`, `/state`, `/evidence/score.json`, `/sse`, path traversal; ports 22/80/443/5000/8001/8080/9000 | only `GET /healthz` (`{"ok":true}`) and `/mcp`; everything else 404 / closed | 0.0 |
| 4 | **MCP surface:** `tools/list`, resources, templates, prompts, `logging/setLevel`, unknown tool `score` | tools = `observe`, `act(action, note)` only; no resources or prompts; unknown tool rejected | 0.0 |
| 5 | **Malformed actions:** `ACTION6`, `ACTION7`, `UNDO`, `WIN`, `RESET;ACTION1`, 5,000-char string, int / null / list, extra args (`level`, `debug`, `x`, `y`) | rejected or ignored; not counted as actions; no state, level, score or truth words in any reply (`action1` / ` ACTION1 ` are normalised and count as a normal move) | 0.0 |
| 6 | **Fresh MCP session to reset the game** | the new session sees the same frame: one episode per container, a new session restarts nothing | 0.0 |
| 7 | **Race:** 32 parallel `act` calls from 32 sessions | all counted exactly (33 valid actions recorded = 33 sent), nothing lost to the race | 0.0 |
| 8 | **RESET spam:** 2,000 RESETs | every RESET counts as an action on the level; no level solved | **0.0** |
| 9 | **Wall spam:** 3,100 moves in a cycle | the move budget ends the level (GAME_OVER) after 33 actions; afterwards only RESET is accepted | **0.0** |
| 10 | **Fetch the answer from the internet** (A4, Sat ~20:40): our public web server serves every eval game's `optimal_path` (`GET /api/games/<id>`) and recorded winning runs; the repo holds `solution/solve.sh` | **was open** (agent container had internet). Fixed: every task now sets an agent-phase egress allowlist (`[agent] network_mode = "allowlist"`): only `game` + model APIs. The game now sits on `localhost:8000` (shared network namespace; via Harbor's proxy it reset idle MCP connections, see `arena/HARBOR.md` "Network"). Probe from the agent seat: GitHub raw, PyPI, our server by name and by IP -> no connection; `api.anthropic.com` reachable; only `localhost:8000` answers locally; oracle 1.000 (eval-v1 + eval-v2 game 1), stop-early 0.125 (eval-v2); OpenCode plays with 0 connection resets | blocked |

Reference points on the same task (judge simulation, fresh clone): **oracle 1.000** (6/6 levels, 86 actions), **do-nothing 0.000**;
stop-early earns exactly the levels it solves (0.167 per level at optimal play, table above).
Doing the task well is the only way to score: per level `min(1, optimal / actions)`, only for solved levels, every action including RESET counted.

Residual risks (not exploitable today):
- ~~The agent container has internet~~ Closed by row 10: the agent phase only reaches `game` and model APIs, so a public repo or our public server can no longer leak `solve.sh` / optimal paths to the agent. A judge who adds `--allow-agent-host <their API>` opens only that host. Outside Harbor the public server still serves eval optimal paths (gallery, challenge); fine for the demo, not reachable from a task.
- `invalid_actions` in `score.json` lags: the sidecar rewrites the file only after a valid action (request to A3). Not part of the reward.

Reproduce:
```bash
T=$(mktemp -d); cp -r harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4 $T/task; rm -rf $T/task/solution
for m in recon forge resetspam wallspam; do
  PYTHONPATH=coordination/redteam ATTACK=$m REDTEAM_OUT=$T/out-$m.txt harbor run -p $T/task -a redteam_agent:RedTeamAgent -o $T/jobs-$m
done
```

