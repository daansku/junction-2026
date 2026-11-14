#!/bin/bash
# Watch SFT v2 / RL training on both GPU boxes (refresh 30 s). Ctrl+C to stop.
K="-i $HOME/.ssh/junction_verda2 -o BatchMode=yes -o ConnectTimeout=15"
while true; do
  clear; echo "SFT v2 training  $(date +%H:%M:%S)"; echo
  echo "=== A100 box (95.216.229.250)"; ssh $K root@95.216.229.250 'bash /root/progress.sh' 2>&1
  echo; echo "=== H100 box (31.22.104.125)"; ssh $K root@31.22.104.125 'bash /root/progress.sh' 2>&1
  sleep 30
done
