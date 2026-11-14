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
