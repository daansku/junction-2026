# A3 -> all: corrections to PLAN.md phase 3 §1 "running right now" (Sat 21:45)

PLAN phase 3 was written from A3's 21:15 notes; three things changed on human orders since:
1. **A3's Modal RL runs are STOPPED** (21:05, human: RL moves to A2's B200). Neither `think-games` nor `think-ctrl`
   reached step 1 on Modal. **There is currently NO control run anywhere.** The only RL run is A2's `think-gridbranch`
   on the B200 (A7 gridbranch v2 tasks, 3072 tokens).
2. **A3's sweeps are draining** (21:13, human: no more evaluations). In-flight games finish by ~23:00, nothing new
   starts. Final coverage: eval-v1 Gemini Flash ~70-90 runs + all baselines; eval-v2 Gemini Flash ~19 games, Kimi ~12;
   h1 Kimi 4; untuned Qwen ~16; h2 board complete (Kimi 10, Gemini Pro 10, Haiku 1). Snapshot:
   `A3-to-all-RESULTS.md`; one refresh at ~23:00.
3. **Capped rows:** Gemini Flash h1 (about half of the runs) and Gemini Pro h2 (8 of 10) were stopped by per-run cost
   caps, so their level counts are lower bounds. They are NOT being rerun (human decision). Label them.
Ready to relaunch if a human says so: `think-ctrl` (generic reasoning-gym puzzles) on one Modal H100, ~$15, code and
data staged (`posttrain/configs/grpo-think.yaml`, `/root/tasks/think-ctrl-s7.jsonl`).
