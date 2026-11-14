#!/bin/bash
# Live SFT progress from py-spy locals (training logs are block-buffered). Prints one bar per train_sft.py process.
. /root/venv/bin/activate 2>/dev/null
for P in $(pgrep -f "python /root/train_sft.py"); do
  row=$(tr '\0' ' ' < /proc/$P/cmdline | grep -oE "sftv2/[a-z0-9-]+" | cut -d/ -f2)
  timeout 15 py-spy dump --pid $P --locals 2>/dev/null > /tmp/pd.$P
  L=$(grep -n "train (/root/train_sft.py\|train (train_sft.py" /tmp/pd.$P | head -1 | cut -d: -f1)
  [ -z "$L" ] && { echo "$row: loading / evaluating"; continue; }
  B=$(sed -n "$L,$((L+60))p" /tmp/pd.$P)
  step=$(echo "$B" | grep -E "^\s+step: " | head -1 | awk '{print $2}')
  total=$(echo "$B" | grep -E "^\s+total: " | head -1 | awk '{print $2}')
  t0=$(echo "$B" | grep -E "^\s+t0: " | head -1 | awk '{print $2}')
  python3 - "$row" "$step" "$total" "$t0" <<'PY'
import sys, time
row, step, total, t0 = sys.argv[1], int(sys.argv[2] or 0), int(sys.argv[3] or 1), float(sys.argv[4] or time.time())
el = time.time() - t0; frac = step / total if total else 0
eta = (el / step * (total - step)) if step else 0
bar = "#" * int(30 * frac) + "-" * (30 - int(30 * frac))
print(f"{row:6s} [{bar}] {step:4d}/{total} {100*frac:5.1f}%  elapsed {el/60:5.1f} min  ETA {eta/60:5.1f} min")
PY
done
[ -z "$(pgrep -f 'python /root/train_sft.py')" ] && echo "(no training running)"
for r in /root/ckpt/*/lora/adapter_model.safetensors; do [ -f "$r" ] && echo "done: $(echo $r | cut -d/ -f4)"; done 2>/dev/null
nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv,noheader
# vLLM servers: model name, port, current load (from each server's log)
for log in /root/vllm*.log; do
  [ -f "$log" ] || continue
  P=$(grep -oE "served_model_name': \['[a-z-]+'\]|lora_modules[^]]*" "$log" | head -1 | grep -oE "arena-[a-z]+" | sort -u | tr '\n' ' ')
  L=$(grep -oE "Avg generation throughput: [0-9.]+ tokens/s, Running: [0-9]+ reqs, Waiting: [0-9]+ reqs" "$log" | tail -1)
  T=$(stat -c %Y "$log"); age=$(( $(date +%s) - T ))
  [ -n "$L" ] && [ $age -lt 120 ] && echo "vllm ${P:-?} | $(echo $L | sed 's/Avg generation throughput: //')"
done
pgrep -f "posttrain.grpo|grpo.py" >/dev/null && echo "GRPO running: $(ls -d /root/ckpt/grpo-*/step-* 2>/dev/null | wc -l) checkpoints saved"
true
