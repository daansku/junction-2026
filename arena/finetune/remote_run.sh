#!/bin/bash
# A3-11 on one rented GPU box (Verda instance, Ubuntu + CUDA image, 1x 80 GB GPU).
# From the laptop (repo root):
#   scp -i ~/.ssh/junction_verda arena/finetune/train_sft.py arena/finetune/remote_run.sh \
#       ~/junction-data/sft/train-v1-h1-8k.jsonl root@<IP>:/root/
#   ssh -i ~/.ssh/junction_verda root@<IP> "SERVE_KEY=<random> nohup bash /root/remote_run.sh > /root/ft.log 2>&1 &"
#   ssh -i ~/.ssh/junction_verda root@<IP> tail -f /root/ft.log
# Then: VERDA_FT_BASE_URL=http://<IP>:8000/v1 and VERDA_FT_KEY=<SERVE_KEY> in .env; model `verda-ft-qwen3-5-9b`.
set -euo pipefail
BASE=${BASE:-Qwen/Qwen3.5-9B}
DATA=${DATA:-/root/train-v1-h1-8k.jsonl}
: "${SERVE_KEY:?set SERVE_KEY (bearer key the vLLM endpoint will require)}"
cd /root
nvidia-smi --query-gpu=name,memory.total --format=csv

python3 -m venv /root/venv && . /root/venv/bin/activate
pip install -q --upgrade pip
pip install -q "torch" "transformers>=4.57" "peft>=0.13" accelerate

echo "== train $(date -u +%H:%M)"
python train_sft.py --base "$BASE" --data "$DATA" --out /root/ckpt/lora --epochs 1 --lr 2e-4 \
    --batch 4 --grad-accum 4 --max-len 2048 --lora-r 16
echo "== merge $(date -u +%H:%M)"
python train_sft.py --merge --base "$BASE" --out /root/ckpt/lora --merged /root/ckpt/merged

echo "== serve $(date -u +%H:%M)"
pip install -q vllm
# Same chat template as the base; text-only prompts. Port 8000 must be reachable (Verda: public IP).
exec vllm serve /root/ckpt/merged --served-model-name arena-ft --max-model-len 4096 \
    --api-key "$SERVE_KEY" --host 0.0.0.0 --port 8000
