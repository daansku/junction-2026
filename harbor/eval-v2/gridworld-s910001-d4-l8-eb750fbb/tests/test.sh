#!/bin/bash
# Separate verifier: read the score the game sidecar wrote (collected by Harbor as an artifact).
set -u
mkdir -p /logs/verifier
python3 - <<'EOF'
import json
try:
    s = json.load(open("/evidence/score.json"))
except Exception as e:  # missing evidence = no credit
    s = {"reward": 0.0, "error": str(e)}
reward = float(s.get("reward", 0.0))
metrics = {"reward": reward}
for k in ("levels_solved", "levels_total", "actions", "invalid_actions"):
    if isinstance(s.get(k), (int, float)):
        metrics[k] = s[k]
metrics["won"] = 1 if s.get("won") else 0
open("/logs/verifier/reward.json", "w").write(json.dumps(metrics))
open("/logs/verifier/reward.txt", "w").write(str(reward))
open("/logs/verifier/score_detail.json", "w").write(json.dumps(s))
print(json.dumps(s))
EOF
