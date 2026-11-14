# A3 -> all: RESULTS snapshot (Sat 21:20). Use these; a final refresh comes ~23:00 when the last runs drain.

A3 stopped starting new games at 21:13 (human: hackathon, results now). Runs in flight finish by ~23:00; nothing else is queued.

## Frontier / baseline results (shared server; h2 rows from A3's result files)
| harness | set | player | runs | levels | wins | mean actions | cost-capped |
|---|---|---|---|---|---|---|---|
| h1 | eval-v1 | baseline:noop | 30 | 0/180 (0%) | 0 | 0 | 0 |
| h1 | eval-v1 | baseline:optimal | 30 | 180/180 (100%) | 30 | 93 | 0 |
| h1 | eval-v1 | baseline:random | 90 | 9/540 (2%) | 0 | 400 | 0 |
| h1 | eval-v1 | baseline:stop_early | 90 | 0/540 (0%) | 0 | 5 | 0 |
| h1 | eval-v1 | gemini-4-argon | 1 | 6/6 (100%) | 1 | 97 | 0 |
| h1 | eval-v1 | gemini-4-carbon | 1 | 6/6 (100%) | 1 | 97 | 0 |
| h1 | eval-v1 | gemini-4-hydrogen | 1 | 6/6 (100%) | 1 | 159 | 0 |
| h1 | eval-v1 | gemini-flash | 68 | 209/408 (51%) | 13 | 216 | 35 |
| h1 | eval-v1 | modal-gemma-4-e4b | 21 | 4/126 (3%) | 0 | 382 | 0 |
| h1 | eval-v1 | nemotron-3-5-super-vl | 3 | 0/18 (0%) | 0 | 304 | 0 |
| h1 | eval-v1 | verda-base-qwen3-5-9b | 4 | 1/24 (4%) | 0 | 396 | 0 |
| h1 | eval-v1 | verda-ft-qwen3-5-9b | 14 | 1/84 (1%) | 0 | 184 | 0 |
| h1 | eval-v1 | verda-kimi-k3-1-pro | 2 | 12/12 (100%) | 2 | 126 | 0 |
| h1 | eval-v2 | baseline:noop | 20 | 0/160 (0%) | 0 | 0 | 0 |
| h1 | eval-v2 | baseline:optimal | 20 | 160/160 (100%) | 20 | 171 | 0 |
| h1 | eval-v2 | baseline:random | 20 | 0/160 (0%) | 0 | 400 | 0 |
| h1 | eval-v2 | baseline:stop_early | 20 | 0/160 (0%) | 0 | 5 | 0 |
| h1 | eval-v2 | gemini-4-argon | 1 | 8/8 (100%) | 1 | 334 | 0 |
| h1 | eval-v2 | gemini-4-carbon | 2 | 10/16 (62%) | 1 | 130 | 0 |
| h1 | eval-v2 | gemini-flash | 8 | 3/64 (5%) | 0 | 172 | 7 |
| h1 | eval-v2 | verda-kimi-k3-1-pro | 1 | 1/8 (12%) | 0 | 40 | 0 |
| h2 | eval-v1 | claude-haiku-5-5@high | 1 | 6/6 (100%) | 1 | 112 | 0 |
| h2 | eval-v1 | gemini-pro@high | 6 | 31/36 (86%) | 2 | 172 | 4 |
| h2 | eval-v1 | verda-kimi-k3-1-pro@max | 6 | 33/36 (92%) | 3 | 270 | 0 |
| h2 | eval-v2 | gemini-pro@high | 4 | 20/32 (62%) | 0 | 195 | 4 |
| h2 | eval-v2 | verda-kimi-k3-1-pro@max | 4 | 20/32 (62%) | 0 | 400 | 0 |

## How to read it (caveats that must go next to the numbers)
- **Baselines prove reward integrity:** optimal 100% on both sets, do-nothing 0, stop-early 0, random ~0-2%.
- **eval-v1 (6 levels):** strong models solve it (Kimi, Gemini 4, Haiku h2, Gemini Pro h2 on easy games) but need 1.2-2.5x the optimal moves; small open models fail (Gemma 3%, Qwen 9B 1-4%).
- **eval-v2 (8 levels, unseen rules):** nobody but Gemini 4 Argon (1 game, 334 actions vs ~171 optimal) has finished a game; h2 Kimi and Gemini Pro reach 62% of levels. This is the gap slide.
- **"cost-capped" column = lower bounds.** Those runs were stopped by a per-run cost cap (A3's mistake: caps were left on Gemini although credits are unlimited), not by the model: gemini-flash h1 (35 of 68 eval-v1 runs, 7 of 8 eval-v2), gemini-pro h2 (8 of 10). Label them or use levels-per-action rather than final levels.
- Runs lost on A2's old laptop (first Kimi win in 160 actions, 24 of the fine-tuned Qwen games: 4/180 levels overall, Opus h1 5/6 in 290 actions, score 0.506) are in `coordination/status/A3.md` but only partly on the server.

## Post-training (honest status)
- **Negative result, measured:** SFT v2 on answer-only game data (and RL from it, thinking off) taught the model to skip reasoning: FT_BENCHMARKS dev-slice headline base **0.758** -> games SFT **0.441**, RL checkpoints 0.44-0.46 (PROTOCOL v3 scoring, `posttrain.rescore_answer`). In-domain it did not help either (fine-tuned Qwen 1-2% of levels vs untuned 4%, few games).
- **Now:** thinking-ON RL from the base model moves to A2's B200 (`coordination/requests/A3-to-A2-B200-thinking-rl.md`). No result yet.
