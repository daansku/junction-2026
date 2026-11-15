#!/bin/sh
# Expert-iteration RL step 3 (H100): LoRA SFT on the policy's own solved episodes, then merge for vLLM.
#   sh train_rft.sh /root/eirl/rft.jsonl
set -e
cd /root/eirl
PATH=/root/venv/bin:$PATH CUDA_VISIBLE_DEVICES=0 /root/venv/bin/python /root/train_sft.py --base "${BASE:-Qwen/Qwen3.5-9B}" \
  --data "$1" --out "${OUT:-/root/ckpt/rft1}/lora" --epochs 1 --lr 1e-4 --batch 1 --grad-accum 8 --max-len 8192 --lora-r 16 --seed 0
PATH=/root/venv/bin:$PATH CUDA_VISIBLE_DEVICES=0 /root/venv/bin/python /root/edge_rover/merge_stack.py --base "${BASE:-Qwen/Qwen3.5-9B}" \
  --lora "${OUT:-/root/ckpt/rft1}/lora" --out "${OUT:-/root/ckpt/rft1}/merged"
echo TRAIN_DONE
