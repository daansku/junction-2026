#!/bin/bash
# SFT v2 on the Verda box (A3-23). Usage: GPU=0 bash run_sft_v2.sh games   (one row per call; run rows in parallel
# with separate calls). Same LoRA recipe as SFT v1 (r16, all language-model linear layers), batch 1 x grad-accum 16
# (effective 16) so two runs fit next to the arena-ft server on GPU 0. Output: /root/ckpt/<row>/lora (adapter).
set -euo pipefail
ROW=$1; GPU=${GPU:-0}
cd /root && . /root/venv/bin/activate
mkdir -p /root/ckpt/$ROW
echo "== $ROW on GPU $GPU start $(date -u +%H:%M)"
CUDA_VISIBLE_DEVICES=$GPU python /root/train_sft.py --base Qwen/Qwen3.5-9B --data /root/sftv2/$ROW.jsonl \
  --out /root/ckpt/$ROW/lora --epochs 1 --lr 2e-4 --batch 1 --grad-accum 16 --max-len 2048 --lora-r 16
cp /root/sftv2/$ROW.stats.json /root/ckpt/$ROW/lora/data_stats.json
echo "== $ROW done $(date -u +%H:%M)"
