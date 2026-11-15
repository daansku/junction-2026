# Harbor + OpenCode run logs (judges' protocol, eval-v2 game 1)

Real runs of the judging protocol (docs/JUDGING.md: reference, three agent runs, do-nothing, stop-early) through
**Harbor + OpenCode over MCP** on the frozen judging set, committed so judges can see a model playing and its score.

- **When / where:** Sun 15.11.2026, 03:18-04:55 EET, A4's machine. Docker 29.8.1, Harbor 0.26.0, OpenCode 1.19.5
  (Harbor installs the latest).
- **Task:** `harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e` (8 levels, difficulty 4; optimal 187 actions).
- **Command** (one per model; the attempts of a model run in parallel, 60-min cap each: the task default when these ran; tasks now give 2 h, commit `5a3f3b2`):
  ```bash
  make judge MODEL=gemini/gemini-4-argon K=3 OUT=harbor/run-logs/eval-v2-s910000-gemini-4-argon-k3     # + baselines
  BASELINES=0 make judge MODEL=gemini/gemini-4-carbon K=3 OUT=harbor/run-logs/eval-v2-s910000-gemini-4-carbon-k3
  BASELINES=0 make judge MODEL=gemini/gemini-3.8-flash K=3 OUT=harbor/run-logs/eval-v2-s910000-gemini-3.8-flash-k3
  BASELINES=0 make judge MODEL=google-openai/gemini-4-argon K=3 OUT=harbor/run-logs/eval-v2-s910000-gemini-4-argon-openai-compat-k3
  ```
- **Reward** = Harbor's `reward.txt`: mean over the 8 levels of min(1, optimal / actions) for solved levels, else 0.
  A capped or crashed attempt is still graded on what it played (score comes from the game container).

## Summary

| Run | Attempts | Rewards | Mean | Levels | Notes |
|---|---:|---|---:|---|---|
| Reference (oracle, BFS optimal path) | 1 | 1.000 | **1.000** | 8/8 | 187 actions |
| **OpenCode + Gemini 4 Carbon** | 3 | 0.743, 0.767, 0.777 | **0.762** | 7/8 each | all three ran the full 60 min; none finished level 8 |
| OpenCode + Gemini 3.8 Flash | 3 | 0.583, 0.143, 0.240 | **0.322** | 6/8, 2/8, 2/8 | two attempts **stopped by themselves** after 7 and 23 min |
| OpenCode + Gemini 4 Argon (native `gemini/`) | 3 | 0.240, 0.250, 0.250 | 0.247 | 2/8 each | **agent-harness crash** after 9-13 min (below) |
| OpenCode + Gemini 4 Argon (`google-openai/`, reasoning high) | 3 | 0.095, 0.105, 0.102 | 0.100 | 1/8 each | two crashed the same way; one ran the full 60 min |
| Stop-early (oracle, level 1 only) | 1 | 0.125 | **0.125** | 1/8 | 31 actions |
| Do-nothing (`nop`) | 1 | 0.000 | **0.000** | 0/8 | |

**The gap on the judges' own harness:** the best frontier agent (Gemini 4 Carbon) scores 0.743-0.777 in three of
three attempts (tight, reproducible), well below the reference 1.000; it solves 7 of 8 levels and uses extra moves on
the ones it solves. Flash shows the "give up early" failure: it quit twice with 6 levels unsolved, which the reward
punishes (0.143, 0.240 vs the 0.125 a stop after level 1 gets).

**Argon is not a clean result.** Gemini 4 Argon sometimes replies with thinking only; OpenCode then resends the
conversation ending with a model turn, which Gemini rejects with HTTP 400 `Requests ending with a model turn are not
supported.`, and OpenCode exits. This is a bug in the agent harness (OpenCode 1.19.5 x Gemini 4), not in the game,
tools or grading; details in [arena/HARBOR.md](../../arena/HARBOR.md) ("Known agent-harness bug").

## Per attempt

### `eval-v2-s910000-gemini-4-carbon-k3`

| run | attempt | reward | levels | actions | agent min | ended |
|---|---|---:|---|---:|---:|---|
| agent-gemini_gemini-4-carbon | `VyAvCN8` | 0.777 | 7/8 | 212 | 60 | 60-min cap (AgentTimeoutError) |
| agent-gemini_gemini-4-carbon | `Wd2TKEz` | 0.767 | 7/8 | 225 | 60 | 60-min cap (AgentTimeoutError) |
| agent-gemini_gemini-4-carbon | `uBcSaup` | 0.743 | 7/8 | 200 | 60 | 60-min cap (AgentTimeoutError) |
| agent-gemini_gemini-4-carbon | **mean of 3** | **0.762** | | | | |

### `eval-v2-s910000-gemini-3.8-flash-k3`

| run | attempt | reward | levels | actions | agent min | ended |
|---|---|---:|---|---:|---:|---|
| agent-gemini_gemini-3.8-flash | `NgUeCdE` | 0.583 | 6/8 | 250 | 60 | 60-min cap (AgentTimeoutError) |
| agent-gemini_gemini-3.8-flash | `qkJDGaH` | 0.143 | 2/8 | 191 | 23 | agent stopped by itself |
| agent-gemini_gemini-3.8-flash | `vTjhB6y` | 0.240 | 2/8 | 84 | 7 | agent stopped by itself |
| agent-gemini_gemini-3.8-flash | **mean of 3** | **0.322** | | | | |

### `eval-v2-s910000-gemini-4-argon-k3`

| run | attempt | reward | levels | actions | agent min | ended |
|---|---|---:|---|---:|---:|---|
| agent-gemini_gemini-4-argon | `MawvsHP` | 0.240 | 2/8 | 60 | 11 | agent harness crashed (NonZeroAgentExitCodeError; APIError: Requests ending with a model turn are not supported (HTTP 400)) |
| agent-gemini_gemini-4-argon | `UUt9rzF` | 0.250 | 2/8 | 63 | 13 | agent harness crashed (NonZeroAgentExitCodeError; APIError: Requests ending with a model turn are not supported (HTTP 400)) |
| agent-gemini_gemini-4-argon | `feYtKsq` | 0.250 | 2/8 | 63 | 9 | agent harness crashed (NonZeroAgentExitCodeError; APIError: Requests ending with a model turn are not supported (HTTP 400)) |
| agent-gemini_gemini-4-argon | **mean of 3** | **0.247** | | | | |
| do-nothing | `duf7Siq` | 0.000 | 0/8 | 0 | 0 | finished |
| reference | `g5TEZnC` | 1.000 | 8/8 | 187 | 0 | finished |
| stop-early-L1 | `bbLJ59n` | 0.125 | 1/8 | 31 | 0 | finished |

### `eval-v2-s910000-gemini-4-argon-openai-compat-k3`

| run | attempt | reward | levels | actions | agent min | ended |
|---|---|---:|---|---:|---:|---|
| agent-google-openai_gemini-4-argon | `CVYfsY5` | 0.095 | 1/8 | 150 | 44 | agent harness crashed (NonZeroAgentExitCodeError; APIError: Requests ending with a model turn are not supported (HTTP 400)) |
| agent-google-openai_gemini-4-argon | `LaUhrSh` | 0.105 | 1/8 | 141 | 9 | agent harness crashed (NonZeroAgentExitCodeError; APIError: Requests ending with a model turn are not supported (HTTP 400)) |
| agent-google-openai_gemini-4-argon | `b9CNaro` | 0.102 | 1/8 | 218 | 60 | 60-min cap (AgentTimeoutError) |
| agent-google-openai_gemini-4-argon | **mean of 3** | **0.100** | | | | |
## Partial runs of other models (15-min cap, proof that they play)

Sun 15.11 05:40-06:10, same task, one attempt each, `BASELINES=0 make judge MODEL=<selector> K=1
OUT=harbor/run-logs/partial-15min/<model> EXTRA="--agent-timeout-multiplier 0.125"` (2 h task cap x 0.125 = 15 min).
**These are not results**: the 15-min cap ends most attempts long before a game can be finished (the full-length
Carbon runs needed the whole hour for 7/8). They show each model connecting through Harbor + OpenCode, playing the
game over MCP and being graded, with the logs to check it.

| Model (OpenCode selector) | Reward (15 min) | Levels | Moves | Ended |
|---|---:|---|---:|---|
| Kimi K3.1 Pro (`verda-kimi/kimi-k3-1-pro`) | 0.389 | 4/8 | 160 | 15-min cap, still playing |
| DeepSeek 4.1 Flash (`verda/deepseek-4-1-flash-1017`) | 0.125 | 1/8 | 43 | stopped by itself |
| Claude Haiku 5.5 (`anthropic/claude-haiku-5-5`) | 0.111 | 1/8 | 76 | stopped by itself |
| DeepSeek V3.2 (`featherless/deepseek-ai/DeepSeek-V3.2`) | 0.000 | 0/8 | 83 | 15-min cap |
| Nemotron 3.5 Super VL (`verda-nemotron/nemotron-3.5-super-vl`) | 0.000 | 0/8 | 187 | 15-min cap |
| GLM 5.3 (`featherless/zai-org/GLM-5.3`) | 0.000 | 0/8 | 4 | one turn of 32,000 output tokens without a move hit OpenCode's per-turn output cap (finish `length`), so OpenCode stopped |

- Two models **stopped by themselves** after level 1 (Haiku, DeepSeek 4.1 Flash), like Gemini 3.8 Flash in the full
  runs: giving up early is a common failure, and the reward pays only for the level solved.
- First tries of Haiku, Kimi and DeepSeek 4.1 Flash (05:40) failed on account problems, not the environment:
  Anthropic `credit balance is too low` and Verda `403 tenant_suspended`. Rerun at 05:51 after the keys were changed
  (the rows above).
- Claude Sonnet / Opus 5.5 were not run (Anthropic budget).

Per attempt (generated by `arena/judge_report.py`):

| run | attempt | reward | levels | actions | agent min | ended |
|---|---|---:|---|---:|---:|---|
| agent-anthropic_claude-haiku-5-5 | `AFteYxm` | 0.111 | 1/8 | 76 | 2 | agent stopped by itself |
| agent-featherless_deepseek-ai_DeepSeek-V3.2 | `EDp7yrb` | 0.000 | 0/8 | 83 | 15 | agent time cap (AgentTimeoutError) |
| agent-featherless_zai-org_GLM-5.3 | `VbyDS2m` | 0.000 | 0/8 | 4 | 9 | length |
| agent-verda_deepseek-4-1-flash-1017 | `XV32rSc` | 0.125 | 1/8 | 43 | 2 | agent stopped by itself |
| agent-verda-kimi_kimi-k3-1-pro | `r5FU4SQ` | 0.389 | 4/8 | 160 | 15 | agent time cap (AgentTimeoutError) |
| agent-verda-nemotron_nemotron-3.5-super-vl | `FShRyJM` | 0.000 | 0/8 | 187 | 15 | agent time cap (AgentTimeoutError) |

## What is in each folder

`<run>/<tag>/<job>/<trial>/`: `result.json` (Harbor's trial result incl. reward and exception),
`verifier/` (`reward.txt`, `reward.json`, `score_detail.json`), `artifacts/evidence/score.json` (the game's score
file), `agent/opencode.txt` (OpenCode event stream: every tool call and reply), `agent/trajectory.json` (ATIF
trajectory), `trial.log`, `exception.txt` when the agent crashed. `<tag>.log` = Harbor console output.
OpenCode's internal state (`agent/opencode/`: SQLite DB and git snapshot, duplicates of `opencode.txt`) was removed
to keep the folder small. Scanned for API keys before committing: none (Harbor stores only the `--ae` templates).

Summary tables regenerate with `python3 arena/judge_report.py harbor/run-logs/<run>`.
