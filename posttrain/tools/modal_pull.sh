#!/bin/bash
# Copy new GRPO checkpoints from the Modal volume to /root/ckpt/<run>/ (A100 box), every POLL seconds.
#   nohup bash posttrain/tools/modal_pull.sh grpo-1 > /root/modal-pull.log 2>&1 &
# Then bench them with posttrain/tools/bench_watch.sh RUN=/root/ckpt/<run> (or hand the paths to A2).
RUN=${1:-grpo-1}; DEST=${DEST:-/root/ckpt/$RUN}; POLL=${POLL:-180}
. /root/modal-venv/bin/activate
mkdir -p "$DEST"
while true; do
  modal volume get --force junction-grpo "/runs/$RUN/log.jsonl" "$DEST/log.jsonl" >/dev/null 2>&1
  modal volume get --force junction-grpo "/runs/$RUN/train.log" "$DEST/train.log" >/dev/null 2>&1
  modal volume get --force junction-grpo "/runs/$RUN/grpo_args.json" "$DEST/grpo_args.json" >/dev/null 2>&1
  for d in $(modal volume ls junction-grpo "/runs/$RUN" 2>/dev/null | grep -oE "step-[0-9]+" | sort -u); do
    if [ ! -f "$DEST/$d/grpo_meta.json" ]; then
      modal volume get --force junction-grpo "/runs/$RUN/$d" "$DEST/" && echo "$(date -u +%H:%M) pulled $d"
    fi
  done
  sleep "$POLL"
done
