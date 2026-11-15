#!/usr/bin/env bash
# One command for the judging protocol (docs/CHALLENGE.md): reference run, do-nothing, stop-early, and K agent runs
# through Harbor + OpenCode on one task, then a summary table.
#
#   make judge                                              # eval-v2 game 1; baselines only (no model, no cost)
#   make judge MODEL=gemini/gemini-4-argon K=3              # + 3 OpenCode runs in parallel (2 h cap each, task default)
#   make judge TASK=harbor/eval-v2/<task> MODEL=anthropic/claude-sonnet-5-5 OUT=/tmp/judge
#   N=1 make judge MODEL=...      # attempts one at a time (default: all K in parallel, up to the 2 h task cap)
#   BASELINES=0 make judge MODEL=...   # agent runs only (e.g. a second model next to a first judge run)
#
# MODEL is an OpenCode selector: anthropic/<model>, gemini/<model>, openai/<model>, or one registered in
# arena/opencode-models.json (verda-kimi/kimi-k3-1-pro, verda-nemotron/..., featherless/...). Keys come from .env
# (coordination/KEYS.md). Model API not in the task's egress allowlist? EXTRA="--allow-agent-host <host>".
# Needs Docker and harbor==0.26.0.
set -uo pipefail
cd "$(dirname "$0")/.."
TASK=${TASK:-harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e}
MODEL=${MODEL:-}
K=${K:-3}
N=${N:-$K}                # attempts in parallel (h2 runs of Gemini 4 Carbon on this game took ~85 min each)
BASELINES=${BASELINES:-1}
SETUP_MULT=${SETUP_MULT:-4}   # OpenCode install is slow when several setups run at once (> 360 s seen with 3)
STOP=${STOP:-1}
OUT=${OUT:-/tmp/junction-judge-$(date +%Y%m%d-%H%M%S)}
EXTRA=${EXTRA:-}
mkdir -p "$OUT"
[ -f .env ] && { set -a; . ./.env; set +a; }

run() {  # tag, harbor args...
  local tag=$1; shift
  echo "== $tag: harbor run -p $TASK $*"
  # shellcheck disable=SC2086
  harbor run -p "$TASK" "$@" $EXTRA -o "$OUT/$tag" >"$OUT/$tag.log" 2>&1 || echo "   (harbor exited $?; see $OUT/$tag.log)"
}

if [ "$BASELINES" = 1 ]; then
  run reference -a oracle
  run do-nothing -a nop
  run "stop-early-L$STOP" -a oracle --ae "ORACLE_STOP_AFTER_LEVELS=$STOP"
fi
if [ -n "$MODEL" ]; then
  CFG=$(python3 -c 'import json;print(json.dumps(json.load(open("arena/opencode-models.json"))))')
  run "agent-${MODEL//\//_}" -a opencode -m "$MODEL" -k "$K" -n "$N" --ak "opencode_config=$CFG" \
    --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' --ae 'VERDA_INFERENCE_KEY=${VERDA_INFERENCE_KEY}' \
    --ae 'FEATHERLESS_API_KEY=${FEATHERLESS_API_KEY}' --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}' --ae 'GEMINI_API_KEY=${GEMINI_API_KEY}' \
    --agent-setup-timeout-multiplier "$SETUP_MULT"
fi

# Keys must never land in a committed log: Harbor stores `--ae` templates, not values, but check anyway.
if grep -rIlE 'AIza[0-9A-Za-z_-]{20}|sk-ant-[0-9A-Za-z_-]{20}|wk-[0-9A-Za-z]{6,}\.ws-|rc_[0-9a-f]{20}|dc_[0-9a-f]{20}' "$OUT" >"$OUT/.secret-hits" 2>/dev/null; then
  echo "WARNING: possible API keys in these files (redact before committing):"; cat "$OUT/.secret-hits"
else
  rm -f "$OUT/.secret-hits"
fi

python3 - "$OUT" "$TASK" <<'EOF'
import json, statistics, sys
from pathlib import Path
out, task = Path(sys.argv[1]), sys.argv[2]
print(f"\nTask: {task}\nResults: {out}\n")
print("| run | trials | reward (each) | mean | levels | actions | errors |")
print("|---|---:|---|---:|---|---|---|")
for tag_dir in sorted(p for p in out.iterdir() if p.is_dir()):
    rows = []
    for res in sorted(tag_dir.glob("*/*/result.json")):
        d = json.loads(res.read_text())
        rw = (d.get("verifier_result") or {}).get("rewards") or {}
        exc = (d.get("exception_info") or {}).get("exception_type")
        rows.append((rw.get("reward", 0.0), f"{rw.get('levels_solved', 0)}/{rw.get('levels_total', '?')}",
                     rw.get("actions", 0), exc))
    if not rows:
        print(f"| {tag_dir.name} | 0 | - | - | - | - | no trials (see {tag_dir.name}.log) |"); continue
    rewards = [r[0] for r in rows]
    errs = ", ".join(sorted({r[3] for r in rows if r[3]})) or "-"
    print(f"| {tag_dir.name} | {len(rows)} | {', '.join(f'{r:.3f}' for r in rewards)} | "
          f"{statistics.fmean(rewards):.3f} | {', '.join(r[1] for r in rows)} | {', '.join(str(r[2]) for r in rows)} | {errs} |")
print("\nAgentTimeoutError on agent runs = the 2 h cap ended the run; the reward still counts what was played.")
EOF
