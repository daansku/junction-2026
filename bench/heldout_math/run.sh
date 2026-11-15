#!/bin/bash
# Held-out MATH test for one model (PROTOCOL amendment v5). Run from the repo root on a GPU box.
#
#   bash bench/heldout_math/run.sh <name> <merged model dir | HF id>
#   bash bench/heldout_math/run.sh <name> --lora <LoRA adapter dir>      (merges onto Qwen3.5-9B first)
#
# Steps: (merge) -> MATH 50 per subject x 7 = 350 items with the frozen generation config -> ANSWER: rescore ->
# paired comparison with base (bench/heldout_math/compare.py). Output: out/heldout/<name>/ (items.jsonl,
# items_v3.jsonl, summary.json, lm_eval/ raw samples). ~4 min on a B200 at GPU_MEM=0.85.
#
# Env: PY (python with vLLM 0.33 + lm-eval 0.4.13; default /root/rl-venv/bin/python on the B200),
#      HF_HOME (default /dev/shm/hf), GPU_MEM (vLLM memory share, default 0.85; results do not depend on it).
set -euo pipefail
NAME=${1:?usage: run.sh <name> <model dir | HF id | --lora adapter dir>}
shift
PY=${PY:-/root/rl-venv/bin/python}
export HF_HOME=${HF_HOME:-/dev/shm/hf} VLLM_USE_FLASHINFER_SAMPLER=0 PYTHONUNBUFFERED=1
export PYTHONPATH=$PWD/bench/src:$PWD/posttrain/src:$PWD/engine/src${PYTHONPATH:+:$PYTHONPATH}
OUT=out/heldout/$NAME
mkdir -p "$OUT"

if [ "${1:-}" = "--lora" ]; then
  ADAPTER=${2:?--lora needs an adapter dir}
  BASE=$(ls -d "$HF_HOME"/hub/models--Qwen--Qwen3.5-9B/snapshots/* 2>/dev/null | head -1)
  BASE=${BASE:-Qwen/Qwen3.5-9B}
  MODEL=/dev/shm/heldout-merged/$NAME
  echo "== merge $ADAPTER onto $BASE -> $MODEL $(date -u +%T)"
  "$PY" arena/finetune/train_sft.py --merge --base "$BASE" --out "$ADAPTER" --merged "$MODEL"
else
  MODEL=${1:?give a model dir, an HF id, or --lora <adapter dir>}
fi

echo "== MATH 350 items: $MODEL $(date -u +%T)"
"$PY" -m bench run --model "$MODEL" --gpu-mem "${GPU_MEM:-0.85}" --only math --name "$NAME" --out "$OUT"
echo "== rescore $(date -u +%T)"
"$PY" -m posttrain.rescore_answer "$OUT" || true
[ "${1:-}" = "--lora" ] && rm -rf "$MODEL"
echo "== compare with base $(date -u +%T)"
"$PY" bench/heldout_math/compare.py "$OUT"
