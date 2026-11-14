#!/bin/bash
# Bench every new RL checkpoint on its own Modal H100 (dev slice, A2's settings), results pulled to /srv/bench/out/.
#   nohup bash posttrain/tools/modal_bench_watch.sh grpo-1 grpo-2 > /root/modal-bench-watch.log 2>&1 &
# Budget guard: at most MAX_LAUNCHES benches in total (default 10, ~$3-4 each on an H100). Spend log:
# /root/modal-bench-launches.tsv (one row per launch). Env: POLL (240 s), REPO (/root/rl-repo).
RUNS=("$@"); [ ${#RUNS[@]} -gt 0 ] || RUNS=(grpo-1 grpo-2)
POLL=${POLL:-240}; MAX_LAUNCHES=${MAX_LAUNCHES:-10}; REPO=${REPO:-/root/rl-repo}
LOG=/root/modal-bench-launches.tsv; OUT=${OUT:-/srv/bench/out}
. /root/modal-venv/bin/activate
cd "$REPO"
touch "$LOG"
while true; do
  for run in "${RUNS[@]}"; do
    for d in $(modal volume ls junction-grpo "/runs/$run" 2>/dev/null | grep -oE "step-[0-9]+" | sort -u); do
      name="rl-$run-$d"
      grep -q "	$name	" "$LOG" && continue
      modal volume ls junction-grpo "/runs/$run/$d" 2>/dev/null | grep -q grpo_meta.json || continue  # not complete yet
      n=$(wc -l < "$LOG")
      if [ "$n" -ge "$MAX_LAUNCHES" ]; then echo "$(date -u +%H:%M) cap $MAX_LAUNCHES reached, not benching $name"; continue; fi
      printf "%s\t%s\t%s\n" "$(date -u +%H:%M)" "$name" "runs/$run/$d" >> "$LOG"
      echo "$(date -u +%H:%M) launch $name"
      (nohup modal run --detach posttrain/modal_grpo.py::bench_dev --adapter "runs/$run/$d" --name "$name" \
         > "/root/modal-bench-$name.log" 2>&1 &)
    done
  done
  # pull results (summary.json is written when a bench run ends; refresh until the app has finished)
  for name in $(cut -f2 "$LOG"); do
    [ -f "$OUT/$name/.pulled" ] && continue
    modal volume ls junction-grpo "/bench/$name" 2>/dev/null | grep -q summary.json || continue
    modal volume get --force junction-grpo "/bench/$name" "$OUT/" >/dev/null 2>&1 && echo "$(date -u +%H:%M) pulled $name"
    if grep -qE "App completed|Stopping app|stopped" "/root/modal-bench-$name.log" 2>/dev/null; then
      touch "$OUT/$name/.pulled"
      # PROTOCOL v3 (human decision 20:50): official rescore, one rule for every row
      (cd /root/posttrain && /srv/bench/.venv/bin/python -m posttrain.rescore_v3 "$OUT/$name" \
         --out "$OUT/rescore_v3-$name.json" 2>&1 | tail -1 | sed "s/^/$(date -u +%H:%M) /" >> /root/rl-v3-headlines.txt)
    fi
  done
  sleep "$POLL"
done
