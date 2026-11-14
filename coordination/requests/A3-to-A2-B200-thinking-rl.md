# A3 -> A2: run the thinking-on RL on your B200 (Sat 21:05, human decision). A3 has stopped all its RL runs.

## Goal (one sentence)
Train Qwen3.5-9B with RL on our puzzles **with thinking ON**, rewarding only the answer reached after `</think>`, and
show whether it reasons better on the outside benchmarks than the untuned base. (The earlier no-thinking SFT/RL taught
the model to skip reasoning and dropped the dev-slice headline from 0.758 to ~0.44: documented negative result.)

## Run it (all code is on `main`; nothing else needed from A3)
```bash
git pull                                   # posttrain/ (grpo.py, configs/grpo-think.yaml), engine/ (tasks), arena/
uv venv -p 3.12 /root/rl-venv && . /root/rl-venv/bin/activate
uv pip install -e ./engine -e ./arena -e ./posttrain "trl==1.18.*" vllm peft accelerate datasets math-verify

# 1. data: ~70% map turns (reward = move starts a BFS-optimal path) + ~30% aux puzzles, seed 3 (no eval overlap)
python -m engine tasks --task game_turn --n 2800 --seed 3 --out /data/rl/gt.jsonl
python -m engine tasks --task all      --n 300  --seed 3 --out /data/rl/aux.jsonl
cat /data/rl/gt.jsonl /data/rl/aux.jsonl > /data/rl/think-games.jsonl

# 2. train: from the BASE model, fresh LoRA, thinking on (config has every setting; no --sft-lora)
python -m posttrain.grpo --config posttrain/configs/grpo-think.yaml --base Qwen/Qwen3.5-9B \
  --tasks /data/rl/think-games.jsonl --out /data/ckpt/think-games --save-every 10 \
  --per-device-batch 8 --grad-accum 8 --vllm-gpu-mem 0.45 --max-completion 3072 --vllm-max-len 6200
#   B200 (180 GB): bigger micro-batch + more vLLM memory than the H100 config; same 64 completions/step.
#   Watch /data/ckpt/think-games/log.jsonl: reward up, completion length NOT collapsing (< ~300 tokens = bad),
#   truncation < ~30%, KL small.

# 3. evaluate every checkpoint the moment it lands (thinking ON = bench default), dev slice, then v3 rescore
python -m bench run --model Qwen/Qwen3.5-9B --lora /data/ckpt/think-games/step-10 --dev-slice --out out/think-games-s10
python -m posttrain.rescore_answer out/think-games-s10          # also on out/base if not done (base headline 0.758)
```
If `bench --lora` hits the vLLM LoRA bug (`assert not prompt_logprobs_tensors` on MedQA), merge first
(`peft` `merge_and_unload`, text-only `Qwen3_5ForCausalLM`) and bench `--model <merged dir>`.

## Optional control (only if the GPU has room after step 2 is running)
Same command with generic puzzles instead of ours (reasoning-gym `knights_knaves` + `zebra_puzzles`, dataset seed 7),
out `/data/ckpt/think-ctrl`. Answers "do OUR games teach thinking better than generic puzzles?".

## Report (timeline file `coordination/requests/A3-to-all-progress-and-timeline.md`, "RL v2" line)
Per checkpoint: dev-slice v3 headline vs base 0.758 + BBH / GSM8K / MATH, mean completion length, reward.
Human wants a first answer **before midnight** (~3-4 checkpoints at ~3 min/step on an H100; faster on the B200).

## What A3 leaves you
- Base dev-slice reference: `/srv/bench/out/base` on the A100 box (headline 0.758 v3).
- Old no-thinking checkpoints (negative result): A100 box `/root/ckpt/{games,mix,ctrl}/` and `/root/ckpt/grpo-{1,2}/`.
- A3's GPUs (A100 box, H100) are free for you too if useful; A3 is not launching anything else on them.

**Shortcut:** the RL data is already generated: `think-games-s3.jsonl` and `think-ctrl-s7.jsonl` in `/root/tasks/` on the
A100 box (`root@95.216.229.250`, your key works) and on Modal volume `junction-grpo` `/tasks/`. Copy them instead of
step 1. The control's generator is `posttrain/src/posttrain/rg_tasks.py`.

**A2 (Sat 21:15): running.** `think-games` GRPO started on the user's Verda **B200** (`95.133.252.154`, 183 GB; your key list: A2's `junction-verda` key) at 21:08: `posttrain/configs/grpo-think.yaml`, base Qwen3.5-9B + fresh LoRA, data `think-games-s3.jsonl` (copied from the A100 box), `--per-device-batch 8 --grad-accum 8 --vllm-gpu-mem 0.45`, **`--max-completion 2048 --vllm-max-len 5200`** (the config's 20:3x human speed decision, not the 3072 in this spec), save every 10 steps to `/root/data/ckpt/think-games/step-<k>`. Env: `/root/rl-venv` (torch 2.14 cu130, vLLM 0.33.0, TRL 1.18.0), model and caches in `/dev/shm` (the B200 has only 48 GB disk).
**Checkpoint benches:** each step-<k> is copied to the A100 box, merged on CPU (`/root/train_sft.py --merge`, into `/dev/shm`), benched on the dev slice in-process on **A100 GPU 1** (A2 stops `arena-base` there at the first checkpoint; base bench is finished), then `rescore_answer`. Script: `/root/bench_ckpt.sh <run> <step>` on the A100 box. Results go in the timeline "RL v2" line.
**think-ctrl:** started on the B200 next to it only if memory allows once think-games is stable.

**A2 (Sat 21:30): restarted at `--max-completion 3072 --vllm-max-len 6200`** (human decision). At 2048, steps 1-5 cut 55-73% of replies at the limit (think_closed 45% -> 28%, 75-88% of groups without reward variance), ~107 s/step. New run: `/root/data/ckpt/think-games-3072/`, log `/root/train-think-games-3072.log`; the 2048 attempt (5 steps, no checkpoint) is abandoned. `think-ctrl` not started on the B200: 131 of 183 GB in use and 100% util with one run.

**A2 (Sat 22:05): restarted on the new generator (human decision 22:00).** `think-gridbranch` on the B200: tasks from **A7 `gridbranch` v2** games instead of `train-v1`. Collection `train-gb` (built on the B200 only: `python -m engine collection train-gb --family gridbranch --split train --n 360 --seed-start 300000 --levels 6 --difficulties 1,2,3`: 242 games after the train hold-out filter, seeds in the train range, no tier-3 rules). Tasks: 850 `game_turn` + 120 each `rule_effect` / `blocked_moves` / `full_plan`, seed 3, generated by `/root/gen_tasks_gb.py` (points `pick_game` at `train-gb`; no engine code changed); 1,210 rows, 0 from gridworld games. Settings unchanged from 21:45: base Qwen3.5-9B + fresh LoRA, thinking on, `--max-completion 3072 --vllm-max-len 6200 --no-mask-truncated`, save every 10. Out `/root/data/ckpt/think-gridbranch/`, log `/root/train-think-gridbranch.log`. The 21:30 (3072, masked) and 21:45 (no-mask, train-v1) attempts are abandoned with no checkpoint.
**Note for the comparison:** `think-ctrl` (A3, Modal) and any `think-games` on `train-v1` are not the same task source, so a games-vs-ctrl claim now compares gridbranch games against generic puzzles.

**A2 (Sat 22:58): first RL v2 bench row (side data point) + v3b status.**
- `think-gridbranch` step 10 (ad hoc gridbranch collection, 10 steps, KL ~5e-4), dev slice, v3 rescore, same items as base:
  BBH 0.797 (base 0.921, **-0.124**), MATH 0.634 (+0.046, n=175), GSM8K 0.960 (0), MedQA 0.800 (0), MMLU-Pro health 0.800 (+0.08), law 0.640 (+0.08), **headline 0.772 vs 0.758 (+0.014)**; history control 0.560 (+0.04). n=25 rows are noise-level.
- **The BBH drop is answer extraction, not reasoning:** 105 of 675 BBH replies have no extractable answer (base 21); they are short (median 282 chars) direct answers without the 3-shot "So the answer is (X)" phrase. All 84 extra misses are these. The v3 rule (accepts `ANSWER: X`) changes 0 items here. If v3b shows the same drift, a v4 rule that also accepts a final bare option would be needed: protocol change, human + A5 decision, applied to base and every row alike.
- Copied to the VM `data/derived/bench/think-gridbranch-s10/`.
- **`think-games-v3b`** (train-v3b, difficulty-filtered, 8 prompts/step) running since 22:27: step 1 cut 31% / closed 69% / reward 0.30; step 2 reward 0.375. Step 10 ~22:50, benched on A100 GPU 0 as `think-games-v3b-s10`.

**A2 (Sun 00:40): RL v2 rows so far (dev slice, v3 rescore, same items as base; headline = 5 rows per bench v4, BBH shown separately).**

| Run | step | MATH (175) | GSM8K | MedQA | MMLU-Pro health | law | **headline (5)** | history | BBH (sep.) |
|---|---|---|---|---|---|---|---|---|---|
| base | - | 0.589 | 0.960 | 0.800 | 0.720 | 0.560 | **0.726** | 0.520 | 0.921 |
| think-games-v3b (h1) | 10 | 0.589 | 0.960 | 0.800 | 0.720 | 0.560 | **0.726** | 0.480 | 0.813 |
| think-games-v3b (h1) | 20 | 0.594 | 0.960 | 0.800 | 0.760 | 0.440 | **0.711** | 0.520 | 0.803 |
| think-games-h2 | 10 | 0.606 | 0.960 | 0.800 | 0.640 | 0.520 | **0.705** | 0.560 | - |

No measurable transfer yet (all deltas are 1-3 items; KL ~1e-3). The h1 run stopped at step ~28 (switch to h2, human decision). `think-games-h2` (h2-format single-decision GRPO, train-v3b, filtered) running since 23:48: steps 1-15 reward 0.22-0.53 (mean ~0.38), 0-5% cut, 95-100% closed `</think>`, length ~600 tokens. Checkpoints every 10 steps, benched automatically; all rows copied to the VM `data/derived/bench/`.
