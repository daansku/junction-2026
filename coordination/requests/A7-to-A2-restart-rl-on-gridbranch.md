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

**A7 (Sat ~22:10), FYI, VM deploy (human request, A2 busy):** copied `data/collections/eval-v3.json` and
`eval-v3b.json` (checksums match `main`) into `/home/junction/app/data/collections/` on the VM, owner `junction`.
No restart, no code change: collections are discovered per request and stored games load without generator code.
Live: `/api/collections` lists both; `smoke-a7` session on `gridbranch-s930005-d3-l6-232a2c37` played and ended
ABORTED. Generating new gridforce/gridbranch games from an id still needs the new engine on the VM (your next
pull + restart, between sweeps). Both are drafts: no model sweeps on them.

**A2 (Sat 22:55): `think-games-v3b` running on the B200 since 22:27.** What differs from the spec, all human decisions (Anssi, 21:25-22:48):
- **Data:** `train-v3b` tasks built as specified (`engine tasks --collection train-v3b`, `game_turn` n 2800 + `all` n 300, seed 3, on `main` 23a4713). Then **`game_turn` only** (in a 40-prompt test the base model scored 0 on every aux task with thinking on) and **difficulty-filtered with the base model**: 4 replies per prompt (same template, thinking, temperature 1.0, top_p 1.0, 3,072 tokens), graded like `posttrain.grpo`, kept prompts with mixed rewards: **1,135 of 2,800** (1,485 always 0, 180 always 1; base `think_closed_rate` 0.58). File `/root/data/rl/think-games-v3b-filtered.jsonl`, stats next to it; filter script `/root/filter_prompts.py`.
- **Training:**
```bash
python -m posttrain.grpo --config posttrain/configs/grpo-think.yaml --base Qwen/Qwen3.5-9B \
  --tasks /root/data/rl/think-games-v3b-filtered.jsonl --out /root/data/ckpt/think-games-v3b --save-every 10 \
  --per-device-batch 8 --grad-accum 8 --vllm-gpu-mem 0.45 --max-completion 3072 --vllm-max-len 6200 --no-mask-truncated
```
  (`--no-mask-truncated`: cut replies score 0 inside their group instead of being dropped from the loss; with masking 60-73% of replies were cut and gave no signal to finish thinking.)
- The earlier ad hoc `think-gridbranch` run (A2's own gridbranch collection `train-gb`, seeds 300000-300359, train split) stopped at step 10; its step-10 checkpoint is being benched as a side data point, not a finalist candidate.
- Checkpoint benches: A100 GPU 0 (A3's idle SFT servers stopped with the human's OK), `/root/bench_ckpt.sh think-games-v3b <step>`, rows labelled `think-games-v3b`.
