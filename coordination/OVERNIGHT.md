# Overnight run plan: Sat 14.11, 03:45 to 09:00

Goal: wake up to real model traces on `dev` (for the UI, the deck and a first gap estimate),
plus Harbor/OpenCode evidence that the judges' path works. `eval-v1` is **not** touched before the 11:00 freeze.

Runner machine: **A4's machine** (it holds the Featherless, Nemotron, Kimi and Gemini keys; A3's machine has none).
All runs that count go to the shared server (`coordination/API_URL`). Keys: `coordination/KEYS.md`.
Judging path: `coordination/JUDGING.md`.

## Blockers before the sweep can start
| # | What | Who | Status |
|---|---|---|---|
| B1 | Shared server runs engine **0.2.0**; `main` is 0.5.0, with different game ids. Pull + restart the shared server **before** the sweep, then **don't restart it until the sweep ends**. | A2 | requested 03:45 |
| B2 | Cost: `overnight-dev` dry-run = **$14.57** (Featherless) + 60 runs on Nemotron/Kimi credits (no per-token price). Cap in `DECISIONS.md` must cover it. | human | cap reads $20 locally; commit DECISIONS.md |
| B3 | `gemini-flash` has no `api_model` yet, so the runner skips it. Pick an id from the live list (e.g. `models/gemini-flash-latest`, `models/gemini-3.8-flash`), with its price from the Gemini docs. | A3 | optional; sweep runs without it |
| B4 | Host machines stay awake: the shared server host and A4's machine (runner + Docker). | human | |

## Schedule
| When | Step | Command (repo root, A4's machine) | Cost |
|---|---|---|---|
| 03:45 | **Smoke** against a local server: catches provider/harness errors. Local traces don't count. | `.venv/bin/python -m arena run arena/sweeps/overnight-smoke.yaml --api http://localhost:8000` | ~$0.49 + 2 credit runs |
| 03:45 | **Harbor + OpenCode + Nemotron**, 1 dev game (judges' path, JUDGING.md row 4) | see JUDGING.md | credits |
| after B1 | **overnight-dev sweep** → shared server: 10 dev games × 3 attempts × 5 models + 4 baselines = 230 runs. Resumable by `run_key`, so after a crash rerun the same command. | `.venv/bin/python -m arena run arena/sweeps/overnight-dev.yaml --api $(cat coordination/API_URL)` | $14.57 + credits |
| after sweep | **Harbor OpenCode × 3 attempts** on 2 dev games with Nemotron (the rubric's "3 agent runs" on the judges' harness) | `harbor run -p <task> -a opencode -m verda-nemotron/nemotron-3.5-super-vl --ak opencode_config=<arena/opencode-nemotron.json as JSON> --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' -k 3` | credits |
| ~07:00 | **Rebuild derived data** on the shared host so the leaderboard and insights show real numbers | A5: `python -m analysis sync && python -m analysis build`, or `POST /api/admin/rebuild` | — |
| 09:00 | Humans: G1 review, look at replays of the overnight runs | humans | — |

Models in `overnight-dev`: `nemotron-3-5-super-vl`, `verda-kimi-k3-1-pro`, `featherless-open` (DeepSeek V3.2),
`featherless-gpt-oss-120b`, `featherless-qwen3-5-9b` (+ `gemini-flash` once B3 is done).
Budgets per run: 400 actions, 500 turns, $1.00, 40 min wall time.

## Not overnight
- `eval-v1` main sweep: after the 11:00 freeze and the 13:00 cost approval (`arena/sweeps/main.yaml`).
- Human baseline: humans playing on the shared server from 09:30.
- Anthropic models: no key on any machine yet.

## Log
- 03:2x Harbor in Docker on A4's machine: oracle 1.0, do-nothing 0, stop-early 1/6 (JUDGING.md).
- 03:48 Harbor + OpenCode + Nemotron finished: reward 0.113, 2/6 levels, 94 actions (15-min cap). Config committed: `arena/opencode-nemotron.json`.
- 03:42 Harbor + OpenCode + Nemotron running on dev game `gridworld-s1000-d1-l6-9b1065f8`: level 1 solved after 53 actions, reward 0.083 so far.
