# A4 → A3: main sweep on eval-v1 is approved (human, Sat 13:55) — please start

The human approved the main sweep and raised the total model budget to **$300** (`coordination/DECISIONS.md`).
Approved spend for the sweeps below: **up to $210**. They are over the $20 per-sweep cap, so run with `--approve-cost`.
Harness `h1` as frozen at 13:30. All runs go to the shared server (`coordination/API_URL`).

## What to run
| Sweep | Games | Attempts | Models | Budgets per run | Est. cost |
|---|---|---|---|---|---|
| `main` | all 30 | 3 | `claude-haiku-5-5` (medium), `gemini-flash` (medium), `featherless-open`; baselines random / optimal / noop / stop_early | max_actions 400, max_cost_usd 2, **max_wall_s 10800** | ~$55 |
| `main-subset-kimi` | first 10 | 1 | `verda-kimi-k3-1-pro` | max_actions 400, max_wall_s 10800 | credits |
| `main-subset-sonnet` | first 10 | 1 | `claude-sonnet-5-5` (medium) | max_actions 400, **max_cost_usd 8**, max_wall_s 10800 | ~$70 |
| `main-opus-subset` | first 5 | 1 | `claude-opus-5-5` (medium) | max_actions 400, **max_cost_usd 16**, max_wall_s 10800 | ~$70 |

Out of this sweep: `nemotron-3-5-super-vl` (see below), `gemini-pro`, `verda-small`. The fine-tuned model is evaluated separately (A3-11).

## Why these numbers (measured, not the dry-run cap)
- The `main.yaml` dry-run says $530 + $120 because it assumes every run hits `max_cost_usd`. Real cost from a Claude Haiku 5.5 game through h1 (A4, local server, 13:00-13:25): **1.9k input + 1.4k output tokens per action** → Haiku ~$0.0009/action (~$0.36 per 400-action run). At the same token counts: Sonnet 5.5 ~$0.018/action (~$7/run), Opus 5.5 ~$0.036/action (~$14/run).
- So `max_cost_usd: 2` would stop Sonnet at ~110 actions and Opus at ~55: a cost cut, not a model failure. Hence 8 and 16 for those sweeps.
- The 1 h wall cap cut Kimi and Gemini off in the pilot (your note). Kimi is ~24 s/action → a 400-action run is up to 2.7 h; 10 runs at concurrency 3 ≈ 9 h. Start Kimi first.
- **Nemotron** (A4, 13:30-13:40): every request waits ~31 s before the first token, then finishes at once; 8 parallel requests took ~198 s each. The deployment serves about one request per 25-30 s across all callers, so concurrency doesn't help and a 400-action game takes ~3.3 h. Report it from the overnight `dev` run (12% of levels) only.

## Fixed on main before h1 froze
- `arena/src/arena/providers/anthropic_provider.py`: `import os` sat above `from __future__ import annotations`, a SyntaxError, so every Claude run failed. Fixed in `c8687db` (13:20); arena tests 54/54. Claude Haiku / Sonnet / Opus 5.5 all answer through the adapter, and Haiku played a full h1 game.

**By when:** start now. Partial results for the G3 review at 20:00; everything finished before the 07:00 number lock.
