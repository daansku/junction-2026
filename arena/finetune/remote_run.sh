#!/bin/bash
# On one rented GPU box (Verda instance, Ubuntu + CUDA image, 1 or 2x A100 40/80 GB, all GPUs used).
# From the laptop (repo root):
#   scp -i ~/.ssh/junction_verda arena/finetune/train_sft.py arena/finetune/remote_run.sh \
#       ~/junction-data/sft/train-v1-h1-4k.jsonl root@<IP>:/root/
#   ssh -i ~/.ssh/junction_verda root@<IP> "SERVE_KEY=<random> nohup bash /root/remote_run.sh > /root/ft.log 2>&1 &"
#   ssh -i ~/.ssh/junction_verda root@<IP> tail -f /root/ft.log
# Then: VERDA_BASE_URL=http://<IP>:8000/v1 and VERDA_FT_KEY=<SERVE_KEY> in .env; model `verda-ft-qwen3-5-9b`.
set -euo pipefail
BASE=${BASE:-Qwen/Qwen3.5-9B}
DATA=${DATA:-/root/train-v1-h1-4k.jsonl}   # 4k examples ~ 45-60 min on 1x A100, ~30 min on 2x
: "${SERVE_KEY:?set SERVE_KEY (bearer key the vLLM endpoint will require)}"
cd /root
nvidia-smi --query-gpu=name,memory.total --format=csv
MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
NGPU=$(nvidia-smi -L | wc -l)
if [ "$MEM" -lt 60000 ]; then BATCH=2; else BATCH=4; fi        # A100 40 GB vs 80 GB
ACC=$(( 16 / (BATCH * NGPU) )); [ "$ACC" -ge 1 ] || ACC=1        # effective batch 16 regardless of GPU count
echo "GPUs=$NGPU batch=$BATCH grad_accum=$ACC"

# Python 3.12 via uv: the image's system Python (3.14 on Ubuntu 26.04) may lack torch/vllm wheels.
command -v uv >/dev/null || { curl -LsSf https://astral.sh/uv/install.sh | sh; }
export PATH="$HOME/.local/bin:$PATH"
[ -x /root/venv/bin/python ] || uv venv -q -p 3.12 /root/venv   # rerun-safe
. /root/venv/bin/activate
uv pip install -q "torch" "transformers>=4.57" "peft>=0.13" accelerate
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.device_count())"

echo "== train $(date -u +%H:%M)"
ARGS=(--base "$BASE" --data "$DATA" --out /root/ckpt/lora --epochs 1 --lr 2e-4 --max-len 2048 --lora-r 16)
if [ "$NGPU" -gt 1 ]; then
  # DDP: one process per GPU, each takes 1/NGPU of every batch (~1.8x faster on 2 GPUs)
  torchrun --standalone --nproc_per_node "$NGPU" train_sft.py "${ARGS[@]}" --batch $BATCH --grad-accum $ACC \
    || { echo "== multi-GPU failed, retrying on 1 GPU"; CUDA_VISIBLE_DEVICES=0 python train_sft.py "${ARGS[@]}" \
         --batch $BATCH --grad-accum $(( 16 / BATCH )); }
else
  python train_sft.py "${ARGS[@]}" --batch $BATCH --grad-accum $ACC
fi
echo "== merge $(date -u +%H:%M)"
python train_sft.py --merge --base "$BASE" --out /root/ckpt/lora --merged /root/ckpt/merged

echo "== serve $(date -u +%H:%M)"
uv pip install -q vllm
# Same chat template as the base; text-only prompts. Port 8000 must be reachable (Verda: public IP).
exec vllm serve /root/ckpt/merged --served-model-name arena-ft --max-model-len 4096 \
    --api-key "$SERVE_KEY" --host 0.0.0.0 --port 8000
