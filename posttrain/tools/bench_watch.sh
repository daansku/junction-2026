#!/bin/bash
# Bench GRPO checkpoints ourselves (no hand-off needed): watches $RUN for step-<k> dirs and runs A2's bench
# dev slice in-process on a whole free GPU (bench's vLLM takes 88% of it), newest unbenched checkpoint first.
#   GPU=1 RUN=/root/ckpt/grpo-1 EVERY=50 nohup bash posttrain/tools/bench_watch.sh > /root/bench-watch.log 2>&1 &
# Env: GPU (1), RUN (/root/ckpt/grpo-1), EVERY (50: bench only steps divisible by it; the final step always),
#      BENCH_PY (python with bench[gpu] installed; default /root/bench-venv/bin/python, else `python`),
#      BENCH_OUT (/root/bench-runs), BASE_RUN (a base or SFT dev-slice run dir to compare against, optional),
#      POLL (120 s), ONCE (1 = bench what exists and exit).
set -uo pipefail
REPO=${REPO:-/root/junction-2026}
GPU=${GPU:-1}
RUN=${RUN:-/root/ckpt/grpo-1}
EVERY=${EVERY:-50}
BENCH_OUT=${BENCH_OUT:-/root/bench-runs}
POLL=${POLL:-120}
BENCH_PY=${BENCH_PY:-/root/bench-venv/bin/python}
[ -x "$BENCH_PY" ] || BENCH_PY=python
NAME=$(basename "$RUN")
cd "$REPO"
mkdir -p "$BENCH_OUT"

pick() {  # newest step dir that is due and not benched yet
  local final
  final=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('steps',''))" "$RUN/grpo_args.json" 2>/dev/null)
  for d in $(ls -d "$RUN"/step-* 2>/dev/null | sort -t- -k2 -n -r); do
    k=${d##*-}
    [ -f "$d/grpo_meta.json" ] || continue
    [ $((k % EVERY)) -eq 0 ] || [ "$k" = "$final" ] || continue
    [ -f "$BENCH_OUT/rl-$NAME-step-$k/.done" ] && continue
    echo "$d"; return
  done
}

while true; do
  d=$(pick)
  if [ -z "$d" ]; then
    [ "${ONCE:-0}" = 1 ] && exit 0
    sleep "$POLL"; continue
  fi
  k=${d##*-}; out="$BENCH_OUT/rl-$NAME-step-$k"
  echo "== bench $d -> $out on GPU $GPU $(date -u +%H:%M) UTC"
  if CUDA_VISIBLE_DEVICES=$GPU "$BENCH_PY" -m bench run --model Qwen/Qwen3.5-9B --lora "$d" --dev-slice \
       --name "rl-$NAME-step-$k" --out "$out" --resume; then
    touch "$out/.done"
    echo "== done step $k $(date -u +%H:%M) UTC"
    [ -n "${BASE_RUN:-}" ] && "$BENCH_PY" -m bench compare --ref "$BASE_RUN" --cand "$out" --out "$out/delta.json"
  else
    echo "== bench FAILED for step $k (left unmarked; retry next poll)"; sleep "$POLL"
  fi
done
