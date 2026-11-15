#!/bin/sh
# B200 round 2: trained model plays (4x on round-1 wins + easy levels) -> retrain from base on round 1+2 wins
# (efficient wins only, rule levels x3) -> merge -> rover-lite eval with JSON repair.
cd /root/a3rl
export HF_HOME=/dev/shm/hf PATH=/root/rl-venv/bin:$PATH CUDA_VISIBLE_DEVICES=0 PYTHONUNBUFFERED=1
PY=/root/rl-venv/bin/python
R1="rollouts/b200-try1.jsonl rollouts/b200-try2.jsonl rollouts/b200-v3.jsonl rollouts/h100.jsonl"
$PY make_r2.py $R1 > r2.log 2>&1
$PY game_rollouts.py --model /dev/shm/ckpt/rftlite/merged --episodes-file r2_episodes.jsonl --obs compact --cap-extra 4 \
  --brief --max-tokens 512 --max-wall 600 --out rollouts/r2.jsonl > ro-b200.log 2>&1
$PY build_rft.py $R1 rollouts/r2.jsonl --out rft2.jsonl --min-reward 0.4 --rule-oversample 3 --eff-dup 0.7 \
  --max-examples 1000 > build.log 2>&1
$PY train_sft_copy.py --base Qwen/Qwen3.5-4B --data rft2.jsonl --out /dev/shm/ckpt/rft2/lora --epochs 1 --lr 1e-4 \
  --batch 1 --grad-accum 4 --max-len 4096 --lora-r 16 --seed 0 > train.log 2>&1
$PY merge_stack.py --base Qwen/Qwen3.5-4B --lora /dev/shm/ckpt/rft2/lora --out /dev/shm/ckpt/rft2/merged \
  --train-sft /root/a3rl/train_sft_copy.py >> train.log 2>&1 && echo MERGED >> train.log
ROVER_LITE=1 $PY run_eval2.py --think --repair --max-tokens 512 --model /dev/shm/ckpt/rft2/merged --name rft4b-r2-lite \
  --seeds 5000-5099 --controls hidden --outdir think > think-rft4b-r2-lite.log 2>&1
echo R2_EVAL_DONE >> train.log
ROVER_LITE=1 $PY run_eval2.py --think --repair --max-tokens 512 --model /dev/shm/ckpt/rftlite/merged --name rft4b-lite-v2 \
  --seeds 5000-5099 --controls hidden --outdir think > think-rft4b-lite-v2.log 2>&1
echo CHAIN_DONE >> train.log
