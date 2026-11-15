#!/bin/sh
# B200 round 3: round-2 model plays FRESH levels (never played), 2 shots each -> retrain from base on unique wins
# of rounds 1-3 (best shot per level, first round that won it) -> merge -> rover-lite eval with JSON repair.
cd /root/rover-rl
export HF_HOME=/dev/shm/hf PATH=/root/rl-venv/bin:$PATH CUDA_VISIBLE_DEVICES=0 PYTHONUNBUFFERED=1
PY=/root/rl-venv/bin/python
while pgrep -f "b200r2.sh" >/dev/null; do sleep 10; done
R12="rollouts/b200-try1.jsonl rollouts/b200-try2.jsonl rollouts/b200-v3.jsonl rollouts/h100.jsonl rollouts/r2.jsonl"
$PY make_r3.py 320 2 $R12 > r3.log 2>&1
$PY game_rollouts.py --model /dev/shm/ckpt/rft2/merged --episodes-file r3_episodes.jsonl --obs compact --cap-extra 4 \
  --brief --max-tokens 512 --max-wall 780 --out rollouts/r3.jsonl > ro-b200.log 2>&1
$PY build_rft.py $R12 rollouts/r3.jsonl --out rft3.jsonl --min-reward 0.4 --rule-oversample 3 --eff-dup 0.7 \
  --max-examples 1400 > build3.log 2>&1
$PY train_sft_copy.py --base Qwen/Qwen3.5-4B --data rft3.jsonl --out /dev/shm/ckpt/rft3/lora --epochs 1 --lr 1e-4 \
  --batch 1 --grad-accum 4 --max-len 4096 --lora-r 16 --seed 0 > train3.log 2>&1
$PY merge_stack.py --base Qwen/Qwen3.5-4B --lora /dev/shm/ckpt/rft3/lora --out /dev/shm/ckpt/rft3/merged \
  --train-sft /root/rover-rl/train_sft_copy.py >> train3.log 2>&1 && echo MERGED >> train3.log
ROVER_LITE=1 $PY run_eval2.py --think --repair --max-tokens 512 --model /dev/shm/ckpt/rft3/merged --name rft4b-r3-lite \
  --seeds 5000-5099 --controls hidden --outdir think > think-rft4b-r3-lite.log 2>&1
echo R3_DONE >> train3.log
