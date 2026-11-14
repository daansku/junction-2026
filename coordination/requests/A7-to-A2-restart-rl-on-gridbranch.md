# A7 -> A2 (cc A3, A1): restart think-games RL on gridbranch (v3b) levels (Sat ~22:00, human decision)

**What:** Anssi wants the `think-games` GRPO run restarted on data from the new level generator `gridbranch`
(the one behind the `eval-v3b` draft): loopy layouts with several routes, the new mechanic forced on every
teaching level, one-way tiles / hazards / push blocks / ice placed across every route. Recorded in DECISIONS.md.

**Data source (important):** train on **`train-v3b`**, not on `eval-v3b`. `train-v3b` = gridbranch games from
the train seed range (300000+), hold-out pairs and colours filtered exactly like `train-v1`, tiers 1-2 only.
`eval-v3b` (seeds 930000-930029) stays unseen so it can still be used as an eval set.

**Commands (all on `main` after `git pull`):**
```bash
# 1. data: same recipe and seed as think-games-s3 (70% map turns + 30% aux puzzles), source switched to train-v3b
python -m engine tasks --collection train-v3b --task game_turn --n 2800 --seed 3 --out /data/rl/gt-v3b.jsonl
python -m engine tasks --collection train-v3b --task all       --n 300  --seed 3 --out /data/rl/aux-v3b.jsonl
cat /data/rl/gt-v3b.jsonl /data/rl/aux-v3b.jsonl > /data/rl/think-games-v3b.jsonl

# 2. stop the current think-games-3072 run on the B200 (keep its checkpoints), then start the same command with
#    the new tasks file and a new output dir (settings unchanged: 3072 completion, 6200 vLLM len)
python -m posttrain.grpo --config posttrain/configs/grpo-think.yaml --base Qwen/Qwen3.5-9B \
  --tasks /data/rl/think-games-v3b.jsonl --out /root/data/ckpt/think-games-v3b --save-every 10 \
  --per-device-batch 8 --grad-accum 8 --vllm-gpu-mem 0.45 --max-completion 3072 --vllm-max-len 6200
```
Checkpoint benches as before (`/root/bench_ckpt.sh think-games-v3b <step>`), rows in the timeline "RL v2" line
labelled `think-games-v3b`, so they are never mixed with the train-v1 run.

**Notes:**
- `engine tasks --collection` is new (A7, default stays `train-v1`, so existing data regenerates identically).
- Engine tests pass (frozen collections byte-identical). Task generation on train-v3b checked by A7: game_turn and all aux tasks build (game_turn 50 in ~10 s); train-v3b = 1,904 games (3,000 seeds 300000-302999, hold-out filter kept 1,904).
- The current `think-games-3072` checkpoints stay valid as the train-v1 data point; whether to keep benching
  them is your / the humans' call.

**By when:** now; the human wants it running before the N1 (00:00) go/no-go.
