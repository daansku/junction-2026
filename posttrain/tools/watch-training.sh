#!/bin/bash
# Live view: training bars, model-server load on both GPU boxes, and every sweep run from this laptop. 30 s refresh.
K="-i $HOME/.ssh/junction_verda2 -o BatchMode=yes -o ConnectTimeout=15"
L=C:/Users/ignac/.cache/junction-arena
while true; do
  clear; echo "A3 live view  $(date +%H:%M:%S)"; echo
  echo "=== A100 box (95.216.229.250)"; timeout 45 ssh $K root@95.216.229.250 'bash /root/progress.sh' 2>&1 || echo '(A100 check timed out)'
  echo; echo "=== H100 box (31.22.104.125)"; timeout 45 ssh $K root@31.22.104.125 'bash /root/progress.sh' 2>&1 || echo '(H100 check timed out)'
  echo; echo "=== sweeps (games done / total, failed)"
  for f in vm-finetune-eval-base-h100 vm-main eval-v2-gemini eval-v2-gemini-redo eval-v2-kimi vm-main-kimi-2 h2-gemini-pro-v1 h2-gemini-pro-v2 h2-kimi-v2c; do
    [ -f $L/$f.log ] || continue
    tot=$(grep -m1 -oE "[0-9]+ to run" $L/$f.log | grep -oE "[0-9]+"); d=$(grep -c " done " $L/$f.log); x=$(grep -c "run failed" $L/$f.log)
    st=$(grep -q '^exit' $L/$f.log && echo finished || echo running)
    lv=$(grep " done " $L/$f.log | grep -v baseline | grep -oE "[0-9]+/[0-9]+ lv" | awk -F'[/ ]' '{a+=$1;b+=$2} END{if(b) printf "%d/%d levels", a, b}')
    printf "%-28s %3s/%-3s done  %2s failed  %-8s %s\n" "$f" "$d" "${tot:-?}" "$x" "$st" "$lv"
  done
  sleep 30
done
