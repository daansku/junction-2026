# Overnight run plan: Sat 14.11, 03:55 to 09:00 (option B)

Goal: wake up to real model traces on `dev` (for the UI, the deck and a first gap estimate),
plus Harbor/OpenCode evidence that the judges' path works. `eval-v1` is **not** touched before the 11:00 freeze.
Keys: `coordination/KEYS.md`. Judging path: `coordination/JUDGING.md`.

## Why option B
The shared server (`coordination/API_URL`, A2's machine) still runs engine **0.2.0**. `main` is 0.5.0, with different game ids, and A2 isn't answering at night.
The runs are therefore recorded on a **separate server on A4's machine** and copied to the shared server in the morning.
This is a documented exception to PLAN.md §3.4 ("local traces are never used for results"). It covers `dev` only: the overnight runs never mix with the `eval-v1` leaderboard.

| | Value |
|---|---|
| Machine | A4's machine (holds the Featherless, Nemotron and Kimi keys) |
| Overnight server | `http://localhost:8100`, engine 0.5.0, `DATA_DIR=~/junction-overnight` (empty at start, separate from A4's test runs in `~/junction-data`) |
| Started with | `DATA_DIR=~/junction-overnight .venv/bin/python -m server serve --port 8100` |
| Sweep | `arena/sweeps/overnight-dev.yaml` |
| Must stay awake | A4's machine (server, runner, Docker) |

## Sizing (from the 03:50 smoke, 1 run per model)
| Model | s / action | $ / action | 150-action run |
|---|---|---|---|
| `featherless-gpt-oss-120b` | 9.6 | 0.00123 | 24 min, $0.18 |
| `featherless-open` (DeepSeek V3.2) | 16.8 | 0.00040 | 42 min, $0.06 |
| `verda-kimi-k3-1-pro` | 23.9 | credits | 60 min |
| `nemotron-3-5-super-vl` | 29.0 | credits | 73 min |
| `featherless-qwen3-5-9b` | 50.3 | 0.00072 | 2 h, **dropped** |

A 400-action run would take 1 to 5.5 h, so the sweep is cut to **4 dev games × 2 attempts, max 150 actions per run**.
That is enough for levels 1 to 3 at 2 to 3× optimal.
Per-model concurrency is set in `arena/models.yaml`: Verda models 3, Featherless 2 each. The sweep pool is 40 so no model waits on another.
The expected finish is about 07:45, when the last Nemotron round completes.

Cost: dry-run **$1.76**; at the measured rate about $2 on Featherless, plus 16 runs on Verda credits.
Each run stops at $1 (`max_cost_usd`), so the worst case is $16, under the $20 cap in `DECISIONS.md`.

## Schedule
| When | Step | Status |
|---|---|---|
| 03:2x | Harbor in Docker: oracle 1.0, do-nothing 0, stop-early 1/6 (JUDGING.md) | done |
| 03:31–03:48 | Harbor + OpenCode + Nemotron on 1 dev game: reward 0.113, 2/6 levels (JUDGING.md) | done |
| 03:45–03:53 | Smoke, 1 game per model on the local test server: all 5 models play through the harness | done |
| 03:55–08:01 | **overnight-dev** → `localhost:8100`: 56 runs (32 model + 24 baseline) | done (Results below) |
| after sweep | Harbor OpenCode + Nemotron, 3 attempts on 1 dev game (rubric: 3 agent runs on the judges' harness): `harbor run ... -k 3`, exact command in JUDGING.md | done 09:12: 0.020 / 0.094 / 0.087, mean 0.067 (JUDGING.md) |
| 09:00 | **Morning copy** to the shared server (below), then A5 rebuilds derived data | done ~12:15: 61/61 runs on the shared server (165 total), `leaderboard.json` rebuilt 12:18 |

Rerun after a crash: the same command resumes by `run_key`.
```bash
.venv/bin/python -m arena run arena/sweeps/overnight-dev.yaml --api http://localhost:8100
```

## Results (sweep finished 08:01)
Packed for the morning copy: `~/overnight-runs.tgz` on A4's machine (61 run folders = 56 sweep runs + 5 abandoned ones from the first start, 1.6 MB).
Summary file: `~/overnight-dev-results.jsonl` (one line per sweep run).

| Player | Runs | Levels solved | Invalid replies / turns | Cost | Wall per run |
|---|---|---|---|---|---|
| baseline: optimal | 4 | 24/24 (100%) | | | |
| `verda-kimi-k3-1-pro` | 8 | **25/48 (52%)**, best run 5/6 | 3 / 1174 | Verda credits | 81 min |
| `nemotron-3-5-super-vl` | 8 | **6/48 (12%)** | 131 / 1331 (10%) | Verda credits | 44 min |
| `featherless-open` (DeepSeek V3.2) | 8 | 0/48 | 3 / 1203 | $0.55 | 38 min |
| `featherless-gpt-oss-120b` | 8 | 0/48 | 3 / 1203 | $1.54 | 24 min |
| baseline: random | 8 | 0/48 | | | |
| baseline: stop_early | 8 | 0/48 | | | |
| baseline: noop | 4 | 0/24 | | | |

- No model finished a game: all 32 model runs hit the 150-action cap. Optimal needs about 108 actions per game.
- Total spend: **$2.09** (Featherless only).
- The two Featherless models are text-only (RLE input) and solved nothing; the two vision models solved levels.
  This is `dev` with a 150-action cap, so it is a first signal for the gap, not a leaderboard result.

## Morning copy (A2 + a human, after A2 restarts the shared server on main)
1. On A4's machine, pack the overnight runs (each run is a folder `runs/<run_id>/` with `meta.json` + `steps.jsonl`):
   ```bash
   tar czf overnight-runs.tgz -C ~/junction-overnight runs
   ```
2. Move `overnight-runs.tgz` to the shared host by hand: a USB stick, or a private file share. Not git: `data/runs/` is gitignored.
3. On the shared host, unpack into its `DATA_DIR`. Run ids are unique (timestamp + hash), so nothing is overwritten:
   ```bash
   tar xzf overnight-runs.tgz -C "$DATA_DIR"
   ```
   Restart the server so `/runs` lists them.
4. A5: `POST /api/admin/rebuild` on the shared host, or `python -m analysis sync && python -m analysis build`.

Alternative if the copy is awkward: A5 runs `python -m analysis sync` against this machine's server through a temporary tunnel. A human would have to start the tunnel.

## Not overnight
- `eval-v1` main sweep: after the 11:00 freeze and the 13:00 cost approval (`arena/sweeps/main.yaml`).
- Human baseline: humans playing on the shared server from 09:30.
- Anthropic and Gemini models: no Anthropic key; `gemini-flash` has no `api_model` yet (A3: pick from the live list, e.g. `models/gemini-flash-latest`, with its price from the docs).

## Log
- 12:21 Morning copy done: shared server (engine 0.5.0, new tunnel) lists all 61 overnight run ids; derived data rebuilt at 12:18 (dev only: Kimi 0.272, Gemini Flash 0.077, Nemotron 0.062, Featherless 0).
- 09:12 Harbor OpenCode + Nemotron rubric set done: 3 scored attempts, mean reward 0.067, each solved 1/6 levels.
- 08:02 Harbor OpenCode + Nemotron, 3 attempts in parallel, 30-min agent cap, started.
- 08:01 Sweep finished, all 56 runs. Packed `~/overnight-runs.tgz`. Results above.
- 04:13 Check: 10 runs active (Kimi 3, Nemotron 3, DeepSeek 2, gpt-oss 2), all stepped within the last 30 s, 0 invalid/errored steps, runner log empty. 24/24 baselines done (oracle 4 WIN). Pace after 15 min: gpt-oss ~9 s/action, DeepSeek and Nemotron ~16–30 s, Kimi ~27 s. Kimi is the bottleneck: 8 runs × ~68 min / 3 slots, so expected finish **~07:30**.
- 04:00 Sweep restarted with pool 40: with pool 10, the Kimi/Nemotron tasks waiting on their per-model limit held every slot, so Featherless and baselines never started. 3 Kimi + 2 Nemotron runs from the first start are left `IN_PROGRESS`/abandoned on :8100: ignore them.
- 03:55 Sweep started.
- 03:53 Smoke stopped after enough data. Overnight server up on :8100 (engine 0.5.0).
- 03:48 Harbor + OpenCode + Nemotron: reward 0.113, 2/6 levels, 94 actions (15-min test cap).
- 03:2x Harbor oracle 1.0 / do-nothing 0 / stop-early 0.167.
