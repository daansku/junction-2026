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

## Update Sat 22:05 (new finished runs; sweeps still draining, final refresh ~23:00)
**eval-v2, runs with NO cost cap (use these for the gap slide):**
| Model (h1) | runs | levels | wins | actions |
|---|---|---|---|---|
| Gemini Flash | 4 | 7/32 (22%) | 0 | 400 (full budget) |
| Kimi K3.1 | 3 | 8/24 (33%) | 0 | 262 mean |
| optimal baseline | 20 | 160/160 | 20 | ~171 |

**eval-v1:** Gemini Flash uncapped runner 114/204 levels (56%), 9 wins in 34 runs; capped runner 113/252 (45%), 35 of
42 runs cost-capped = lower bound. h1 Kimi subset: WON s900000 (113 actions) and s900003 (139), 5/6 on s900001 and
s900002 (time cap).
**Fine-tune in-domain (h1, eval-v1):** untuned Qwen3.5-9B **1/96 levels (1%)** on 16 games; SFT v1 fine-tuned 4/180
(2%). The first fine-tune did not help on our games either: confirms the negative result.
Still draining: ~16 eval-v2 Gemini Flash games, ~9 eval-v2 Kimi games (3 Kimi runs lost to Verda's rate limit, 429).

## Update Sat 23:10: h2b on eval-v2: frontier models WIN these games (early, read the caveats)
Harness **h2b** (= h2 + up to 5 actions per model call, list stops early when a level ends / the game ends / an action
changes nothing; smaller context: last 2 frames, last 3 reasoning blocks; every action counted and scored as in h2).
Built at 22:30 only to make complete runs faster (human: "same sweeps, much less time"). Sweep `h2b-eval-v2.yaml`:
frozen 4 eval-v2 games (s910000-s910003) x 3 attempts, effort high, no cost cap, all 60 runs at once from 22:32.

**Finished at 23:10: 20 of 20 are full WINS (8/8 levels).**
| model | wins so far | games won | actions |
|---|---|---|---|
| Gemini 4 Argon | 8 | s910001 x3, s910002 x3, s910003 x2 | 143-224 |
| Gemini Flash | 7 | s910000 x1, s910002 x3, s910003 x3 | 165-298 |
| Gemini 4 Carbon | 5 | s910002 x3, s910003 x2 | 146-204 |
| Gemini Pro | 0 finished (live: up to 7/8 levels) | | |
Under h1 and h2 **no model won any of these 4 games** (h2 Kimi best 7/8 in 400 actions; h1 Gemini Flash 0-4/8).

Caveats:
- **Biased early sample:** wins end early; non-wins still play to 400 actions. Full board ~23:45-00:30.
- **The gap depends on the harness.** Same games, models, effort; only the action interface and context changed.
  Likely drivers: multi-step moves (fewer chances to lose the plan between calls), the "action changed nothing"
  stop (free bump signal), shorter context. Not separated (no time for ablations).
- **Kimi: all 12 h2b runs died with Verda `403 project is suspended`** (account issue, human checking). No Kimi h2b row.
- 4 Gemini runs crashed (3 empty provider replies, 1 rate limit, 429). Not rerun.

**What this means for the claims (A1/A5/A6 decide the framing):** "frontier models fail" holds under the
one-action-per-call harnesses (h1, h2) but **not** under h2b on these 4 games. Either report it as a harness
sensitivity finding (the gap is about the interaction protocol, not the rules alone) or test on harder games.
Do not quote h2b and h2 numbers as one board.

### Kimi K3.1 on h2b (23:15): incomplete, Verda account suspended, no more Verda (human decision)
All 12 runs died at 130-267 of 400 actions (`403 project is suspended`). Levels at cutoff, 3 attempts per game:
s910000 2/1/1, s910001 6/4/2, s910002 5/5/1, s910003 4/4/2.
- **Measured (quote only this): >= 37/96 levels (39%), 0 wins at cutoff.** Lower bound.
- Projection, NOT measured (each run's own pace extended to 400 actions, capped at 8): ~60-70% of levels,
  ~3-4/12 wins. Consistent with Kimi h2 on the same games (7, 7, 5, 1 of 8 = 62%, 0 wins). Label it as an estimate.
- Kimi trails Gemini under h2b: at ~220 actions Kimi had 2-6 levels; Gemini Flash/Argon had 6-7 or had already won.

### h2b eval-v2 update 23:30: Argon, Carbon, Flash final (Pro still running, ETA ~00:15-00:45)
| model (effort high) | completed runs | wins | levels (completed runs) | crashed (not rerun) |
|---|---|---|---|---|
| Gemini 4 Carbon | 12/12 | **12** | 96/96 (100%) | 0 |
| Gemini 4 Argon | 8/12 | **8** | 64/64 (100%) | 4 (empty provider reply) |
| Gemini Flash | 9/12 | **7** | 69/72 (96%); losses 7/8 on s910001, 6/8 on s910000 | 3 (rate limit 429 / empty reply) |
| Kimi K3.1 | 0/12 | - | >= 37/96 at cutoff (Verda suspended); see row above | 12 |
Every game was won by at least one model; Carbon won all 4 games in all 3 attempts. Crashed runs are not losses.
Same caveat as 23:10: h1/h2 on these games had 0 wins; the interaction protocol, not the rules alone, drives the gap.
