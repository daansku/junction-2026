#!/usr/bin/env bash
# Smoke test: does each model play through Harbor + OpenCode over MCP?
# Short runs (default 3 min agent cap) on one task; checks the model connects, calls the game tools and
# makes actions. Rewards from these runs are NOT results (the cap cuts every run short).
#
#   bash arena/harbor_models_smoke.sh [OUT_DIR] [MODEL ...]
#   CAP=0.05 TASK=harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e PAR=3 bash arena/harbor_models_smoke.sh /tmp/smoke
#
# Needs Docker, harbor==0.26.0 and the keys in .env (docs/KEYS.md).
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-/tmp/harbor-models-smoke}; shift || true
TASK=${TASK:-harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e}
CAP=${CAP:-0.05}          # agent timeout multiplier: task default 3600 s x 0.05 = 3 min
PAR=${PAR:-3}             # harbor runs at once (OpenCode install is slow with many in parallel)
MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  MODELS=(
    anthropic/claude-haiku-5-5
    gemini/gemini-4-argon
    gemini/gemini-4-carbon
    gemini/gemini-3.8-flash
    verda-kimi/kimi-k3-1-pro
    verda-nemotron/nemotron-3.5-super-vl
    featherless/deepseek-ai/DeepSeek-V3.2
  )
fi
set -a; . ./.env; set +a
CFG=$(python3 -c 'import json;print(json.dumps(json.load(open("arena/opencode-models.json"))))')
mkdir -p "$OUT"

run_one() {
  local m=$1 tag=${1//\//_}
  harbor run -p "$TASK" -a opencode -m "$m" \
    --ak "opencode_config=$CFG" \
    --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' \
    --ae 'VERDA_INFERENCE_KEY=${VERDA_INFERENCE_KEY}' \
    --ae 'FEATHERLESS_API_KEY=${FEATHERLESS_API_KEY}' \
    --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}' \
    --agent-timeout-multiplier "$CAP" --agent-setup-timeout-multiplier 2 \
    -o "$OUT/$tag" >"$OUT/$tag.log" 2>&1
  echo "done $m (exit $?)"
}

i=0
for m in "${MODELS[@]}"; do
  run_one "$m" &
  i=$((i + 1))
  if [ $((i % PAR)) -eq 0 ]; then wait; fi
done
wait
python3 arena/harbor_smoke_report.py "$OUT"
