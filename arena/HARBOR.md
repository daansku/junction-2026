# Running our games in Harbor (the AfterQuery judging harness)

The judges rerun everything with **Harbor + OpenCode over MCP**: a reference run, three agent runs,
a do-nothing baseline and a stop-early baseline, then spend 15 minutes hunting reward exploits.
This folder turns each game into a Harbor task they can run as-is.

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
| `task.toml` | schema 1.1; `game` MCP server (`streamable-http`, `http://localhost:8000/mcp`); agent egress allowlist; **separate** verifier; `/evidence/score.json` collected from the `game` service as an artifact |
| `instruction.md` | tools, actions, "find the goal yourself", scoring; no rules, no colours, no numbers |
| `environment/Dockerfile` | the agent's container: plain ubuntu, **no game code** |
| `environment/docker-compose.yaml` | adds the `game` sidecar (built from `environment/game/`) |
| `environment/game/` | engine + `arena.harbor.sidecar` + a one-game collection |
| `tests/test.sh` | separate verifier: reads the collected `/evidence/score.json` -> `/logs/verifier/reward.json` + `reward.txt` |
| `solution/solve.sh` | oracle: replays the optimal path through the MCP tools |

## Reward
ARC-AGI-3 style: mean over levels of `min(1, optimal_moves / actions_on_level)` for solved
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

## Network: the agent reaches only the game and model APIs
Our public web server serves the eval games with their optimal paths and every recorded run, and the repo holds
`solution/solve.sh`. An agent with open internet could fetch either and replay the answer. So every task sets an
**egress allowlist for the agent phase** (`[agent] network_mode = "allowlist"`, Harbor's Docker egress control):
the agent can reach the game and the model APIs in `allowed_hosts` (Anthropic, Google, OpenAI,
OpenRouter, Verda, Featherless, NVIDIA, Together, Fireworks, DeepSeek, Moonshot, xAI, Mistral) and nothing else.
Setup (installing OpenCode) and the verifier keep their default network.

**Your model API is not in the list?** Add it: `harbor run ... --allow-agent-host <host>` (repeatable).

**The game is at `http://localhost:8000/mcp`.** With egress control on, Harbor runs the `game` service inside its
egress sidecar's network namespace, next to the agent (shared network only: separate filesystem and processes).
Local traffic skips Harbor's transparent proxy (gost). A first version kept `game` as its own host on the compose
network: that traffic went through the proxy, which reset idle MCP connections, so `act` failed with `ECONNRESET`
after slow model turns (Haiku 9, Nemotron 11, DeepSeek 4 of 4 calls in 3-min runs; 0 without the allowlist). On
localhost: 0 resets (Nemotron 24 acts, DeepSeek 10). Do not add `expose` or `networks` to `game`: Docker refuses
`expose` in a shared namespace, and an own network puts the proxy back in the path.

Red team from the agent's seat with the allowlist on (`coordination/redteam/attack.py`, `ATTACK=recon`, Sat 21:00,
committed `eval-v1` game 1): GitHub raw, PyPI, our web server (by name and by IP) unreachable; `api.anthropic.com`
reachable; on localhost only `:8000` answers (`/healthz`, `/mcp`), no game files visible. Committed tasks: oracle
1.000 (eval-v1 game 1, 6/6, 86 actions; eval-v2 game 1, 8/8, 187), stop-early 0.125 (eval-v2, 1/8).

## Other models through OpenCode
`arena/opencode-models.json` registers the OpenAI-compatible endpoints (Verda Kimi + Nemotron, Featherless).
Anthropic and Gemini use OpenCode's built-in providers (`anthropic/<model>`, `gemini/<model>`).

```bash
set -a; . ./.env; set +a
CFG=$(python3 -c 'import json;print(json.dumps(json.load(open("arena/opencode-models.json"))))')
harbor run -p harbor/eval-v2 -a opencode -m <selector> --ak "opencode_config=$CFG" \
  --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' --ae 'VERDA_INFERENCE_KEY=${VERDA_INFERENCE_KEY}' \
  --ae 'FEATHERLESS_API_KEY=${FEATHERLESS_API_KEY}' --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}' -k 3
```
- Gemini: OpenCode's `google` provider reads `GOOGLE_GENERATIVE_AI_API_KEY`, not `GEMINI_API_KEY`; without the
  `--ae` above it fails with `ProviderAuthError ... API key is missing`.
- Anthropic: Harbor forwards `ANTHROPIC_API_KEY` from the host by itself.
- Smoke test of every model (3-min cap, checks the model connects and plays): `bash arena/harbor_models_smoke.sh <out>`,
  summary table from `python3 arena/harbor_smoke_report.py <out>`. Capped-run rewards are not results.

Smoke results (A4, Sat 14.11 20:30-21:10, eval-v2 game 1, 3-min agent cap, Docker 29.8.1 + Harbor 0.26.0). "Works" =
the model connects and its game actions count. Every model below plays through Harbor + OpenCode:

| Selector | Actions in 3 min | Notes |
|---|---:|---|
| `anthropic/claude-haiku-5-5` | 78 / 31 | first run stopped on its own at 1/8 levels ($0.005); second run under the allowlist |
| `gemini/gemini-4-argon` | 20 | needs `GOOGLE_GENERATIVE_AI_API_KEY` |
| `gemini/gemini-4-carbon` | 10 | slow turns |
| `gemini/gemini-3.8-flash` | 31 | 1/8 levels; also used `bash` |
| `verda-kimi/kimi-k3-1-pro` | 31 / 8 | 1/8 levels in the first run; spends turns in `bash` (9 calls in the second) |
| `verda-nemotron/nemotron-3.5-super-vl` | 23 | allowlist + localhost: 0 resets |
| `featherless/deepseek-ai/DeepSeek-V3.2` | 10 | text only; allowlist + localhost: 0 resets |
| `featherless/zai-org/GLM-5.3` | 1 | very long turns; with `output` 8192 it stopped at the output limit (`length`), now 32768 |

Not tested: `anthropic/claude-sonnet-5-5` and `claude-opus-5-5` (Anthropic key nearly empty); same provider path as Haiku.

### Full-length runs (judges' protocol): `harbor/run-logs/`
`make judge MODEL=<selector> K=3` on eval-v2 game 1, 60-min cap per attempt, attempts in parallel (Sun 15.11
03:18-04:55, Docker 29.8.1, Harbor 0.26.0, OpenCode 1.19.5). Per-attempt tables, logs and trajectories:
[harbor/run-logs/README.md](../harbor/run-logs/README.md).

**Known agent-harness bug: OpenCode + Gemini 4 Argon.** Gemini 4 sometimes answers with thinking only (no text, no
tool call; OpenCode logs finish reason `unknown`). Since v1.18.21 OpenCode then continues the turn by resending the
conversation, which now ends with a model turn, and Gemini rejects that with HTTP 400 `Requests ending with a model
turn are not supported.` OpenCode exits (`NonZeroAgentExitCodeError`) and the attempt ends early; the reward still
counts what was played (graded from the game container as usual). All three Argon attempts on the native `gemini/`
route ended this way after 9-13 min; the OpenAI-compatible route (`google-openai/gemini-4-argon`, registered in
`arena/opencode-models.json` with `reasoningEffort: high`) hits the same 400. Gemini 4 Carbon and Gemini 3.8 Flash
did not hit it in 60-min runs. Not an environment bug: the game, MCP tools and grading behave normally; nothing in
the task can avoid it. No OpenCode release fixes it as of 1.19.5 (PR anomalyco/opencode#40142, closed unmerged,
covered only the `length` case).

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
