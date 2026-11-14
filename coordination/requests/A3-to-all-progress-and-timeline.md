# A3 -> all: progress + timeline (Sat 19:15). Updated by A3 as things land.

## Results so far (shared server, eval-v1 frozen unless noted)
- **h1 eval-v1, Gemini Flash (medium):** d1 games WON 3/3 (157-173 actions, optimal 86-92); d2/d3 3-4/6 levels at the 400-action cap.
- **h1 eval-v2, Gemini Flash:** 0-1 of 8 levels in 6 games, BUT the $2/run cost cap stopped them at 105-215 actions (optimal ~173): a lower bound, label it.
- **h2 (lab-style harness):** Kimi K3.1 (max) WON 3 eval-v1 games (103-204 actions), 5/6 on two d2/d3, 5/8 + 7/8 on eval-v2. Gemini Pro (high) WON both d1 games (98, 131), 4/8 on eval-v2 ($18 cap). Haiku WON s900000 in 112. => the gap holds on harder games, closes on easy ones.
- **Opus 5.5 (h1):** hard d3 game 5/6, 290 actions vs 81 optimal, score 0.506.
- **Fine-tuned Qwen3.5-9B SFT v1 (h1):** 4/180 levels. Untuned base: rerunning on its own H100 server (the shared one timed out).
- **SFT v2 trained (all three):** `games` val loss 2.62->0.23, `mix` 1.37->0.94, `ctrl` 1.51->1.10 (2.50M tokens each, token-matched). Served on A100 port 8002 as `arena-{games,mix,ctrl,sftv1}`.

## RL
- **grpo-1** (Modal H100, started 19:48): SFT v2 `games` -> GRPO on 70% `game_turn` + 30% aux, 150 steps, ckpt every 25.
  20:10: step 9/150, ~80 s/step (ETA ~23:15), reward 0.25-0.30, game_turn 0.22-0.29, KL 0.003-0.007, no errors.
- **grpo-2** (Modal H100, started 20:08, human-approved second run): `games` -> GRPO on `game_turn` only (seed 1),
  80 steps, ckpt every 20 (ETA ~22:15). Same lr/KL/G.
- **Bench of RL checkpoints:** each new step-<k> of either run is MERGED into Qwen3.5-9B and benched on the dev slice
  on its own Modal H100 (`modal_grpo.py::bench_dev`, `posttrain/tools/modal_bench_watch.sh`, A2's generation.yaml
  unchanged), results pulled to `/srv/bench/out/rl-<run>-step-<k>/`. Merged, not `--lora`: vLLM 0.33's LoRA path
  asserts on loglikelihood requests (MedQA), which is what crashed :8002 at 19:50.
  Baseline for the same items: `games` merged, on Modal (`out/sft-games-dev-merged`, started 20:09).
  The earlier `base-dev` run was killed at 15:17 (no rows); the A100 LoRA attempt of the baseline was stopped (GPU 0 freed).
- **In-domain check:** `modal run posttrain/modal_grpo.py::evaluate` = mean game_turn reward on 200 held-out prompts (seed 2).
- **Modal spend (cap EUR 100, user's rule):** grpo-1 <= ~$16 (4 h cap), grpo-2 ~$10, benches ~$3-4 each (max 10 launches
  -> <= ~$40), image builds/failed starts ~$1, stopped LoRA bench of games ~$1. Committed worst case ~$68.

## Timeline (Helsinki)
| When | What | Who uses it |
|---|---|---|
| ~19:40 | SFT v2 `ctrl` done; served with games/mix on A100 port 8002 (A2 told before restart) | A2 bench |

| 19:48 | **GRPO RL RUNNING on a Modal H100** (started) (fallback: our H100 ~20:30), from the SFT v2 `games` adapter (decided 19:35 without waiting for bench), on A1's `game_turn` (h1 map turns, ~70%) + aux tasks (~30%); ~3 h | A3 benches checkpoints on the dev slice |
| ~21:30 | h2 board complete (Kimi + Gemini Pro; capped Gemini Pro eval-v2 runs redone after) | A5 h2 board |
| ~22:00 | eval-v2 Gemini Flash redo of the 7 capped games | A5 |
| ~23:30 | h1 Kimi subset (10 games) | A5 |
| ~01:00 | eval-v2 Gemini Flash (all 30, uncapped), eval-v2 Kimi (30, now 12 in parallel), untuned-Qwen game eval (H100) | A5 leaderboard, fine-tune result |
| ~01:30 | h1 main sweep (Gemini Flash 30x3 + baselines; now 40 in parallel) | A5 leaderboard |
| ~00:30 | SFT v2 games/mix/ctrl on the FT_BENCHMARKS suite (restarted 20:15: the multi-LoRA vLLM server crashed at 19:50 on a vLLM 0.33 bug with loglikelihood requests; now merged models, one plain server each on A100 GPU 0); SFT v1 after; base bench (A2's run) continuing | transfer claim |
| ~23:00-03:00 | RL checkpoints benched, finalist by the pre-registered rule, finalist on both boards | final numbers |
| 07:00 | numbers lock | all |

## Pending / risks
- **Budget (decided 19:25):** Gemini credits are unlimited, so the main sweep keeps 3 attempts and Gemini runs get caps that never cut a run short. eval-v2 Gemini Flash is being rerun at $15/run (the first 7 runs were stopped by a $2 cap: use the uncapped run per game, attempt 1 for s910000-s910006). Gemini Pro h2 eval-v2 runs capped at $18 will be redone the same way.
- Verda inference was suspended ~18:40 (Kimi 403); new key in since 19:00, Kimi runs restarted.
- DeepSeek V3.2 removed from Featherless: no eval-v1 DeepSeek row.
- GPUs: A100 GPU0 = ctrl training + LoRA server 8002 (bench); A100 GPU1 = `arena-base` 8001 (A2 bench only); H100 = base game eval until ~20:30, then RL. Modal (~EUR 100) available on the A100 box for extra bench GPUs.
