#!/bin/bash
# A3-25 GRPO launcher for one GPU box (H100 or A100). Own venv (/root/rl-venv) so TRL/vLLM pins never touch the
# SFT or bench environments. Usage (on the box, repo checked out at $REPO):
#   SFT_LORA=/root/ckpt/games/lora GPU=0 bash posttrain/run_grpo.sh
#   tail -f /root/ckpt/grpo-1/train.log ; tail -f /root/ckpt/grpo-1/log.jsonl
# Env: SFT_LORA (required), GPU (0), CONFIG (posttrain/configs/grpo-1-h100.yaml), OUT (/root/ckpt/grpo-1),
#      STEPS / SAVE_EVERY (override the config), N_PER_TASK (400 prompts per task type), MIN_FREE_MB (70000),
#      EXTRA (more grpo.py flags, e.g. "--thinking --max-completion 2048").
set -euo pipefail
REPO=${REPO:-/root/junction-2026}
: "${SFT_LORA:?set SFT_LORA to the SFT v2 adapter dir, e.g. /root/ckpt/games/lora}"
GPU=${GPU:-0}
CONFIG=${CONFIG:-posttrain/configs/grpo-1-h100.yaml}
OUT=${OUT:-/root/ckpt/grpo-1}
N_PER_TASK=${N_PER_TASK:-400}
MIN_FREE_MB=${MIN_FREE_MB:-70000}
cd "$REPO"
[ -f "$SFT_LORA/adapter_config.json" ] || { echo "no adapter at $SFT_LORA"; exit 1; }

FREE=$(nvidia-smi -i "$GPU" --query-gpu=memory.free --format=csv,noheader,nounits | tr -d ' ')
echo "GPU $GPU free ${FREE} MB"
if [ "$FREE" -lt "$MIN_FREE_MB" ]; then
  echo "GPU $GPU has only ${FREE} MB free (< $MIN_FREE_MB): stop the vLLM server on it first, or MIN_FREE_MB=... to force"
  nvidia-smi -i "$GPU" --query-compute-apps=pid,process_name,used_memory --format=csv
  exit 1
fi

command -v uv >/dev/null || { curl -LsSf https://astral.sh/uv/install.sh | sh; }
export PATH="$HOME/.local/bin:$PATH"
[ -x /root/rl-venv/bin/python ] || uv venv -q -p 3.12 /root/rl-venv
. /root/rl-venv/bin/activate
# vllm 0.33.0 = bench's pin and inside TRL 1.18's supported range (0.23-0.33)
uv pip install -q "vllm==0.33.0" "trl==1.18.0" "peft>=0.13" accelerate datasets pyyaml -e engine -e posttrain
python -c "import torch, trl, vllm, transformers; print('torch', torch.__version__, 'trl', trl.__version__, 'vllm', vllm.__version__, 'transformers', transformers.__version__, 'cuda', torch.cuda.is_available())"

mkdir -p "$OUT" /root/tasks
TASKS=/root/tasks/rl-s0-n$N_PER_TASK.jsonl   # seed 0 = train split; never seed 1 (bench dev slice convention)
[ -s "$TASKS" ] || python -m engine tasks --task all --n "$N_PER_TASK" --seed 0 --out "$TASKS"

ARGS=(--config "$CONFIG" --sft-lora "$SFT_LORA" --tasks "$TASKS" --out "$OUT")
[ -n "${STEPS:-}" ] && ARGS+=(--steps "$STEPS")
[ -n "${SAVE_EVERY:-}" ] && ARGS+=(--save-every "$SAVE_EVERY")
# shellcheck disable=SC2206
[ -n "${EXTRA:-}" ] && ARGS+=($EXTRA)
echo "== grpo start $(date -u +%H:%M) UTC: ${ARGS[*]}"
CUDA_VISIBLE_DEVICES=$GPU PYTHONUNBUFFERED=1 nohup accelerate launch --num_processes 1 --mixed_precision bf16 \
  -m posttrain.grpo "${ARGS[@]}" > "$OUT/train.log" 2>&1 &
echo "pid $! -> $OUT/train.log ; checkpoints $OUT/step-<k> ; bench: posttrain/tools/bench_watch.sh"
