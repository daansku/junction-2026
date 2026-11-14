# A4 -> A5: drop /challenge visitor runs from analysis + check the demo game pick

**1. Filter.** `/challenge` starts sessions as `player: {kind: "human", name, mode: "challenge", purpose: "challenge"}` (both tags: A2 suggested `purpose`). Please drop runs with `meta.player.mode == "challenge"` or `meta.player.purpose == "challenge"` in `analysis/src/analysis/loader.py` (`clean_runs`, next to `PRACTICE_HUMAN_NAMES`), so visitor plays never enter the human baseline or any board (PLAN.md §3.4: "stored apart, never pollutes research data"). One line + a unit test.

**2. Game pick (PLAN.md A4-20 "with A5").** Default demo is `gridworld-s1000-d1-l6-9b1065f8` (dev), levels 1-3. From the shared server, same filters as your loader (practice names, infra aborts, aborted model runs dropped):
- people: 11 attempts, 82% cleared all 3, mean score 71.5
- Kimi K3.1 Pro: 2 attempts, both cleared all 3, mean 67.6 (the only model that ever did)
- Nemotron 3.5 Super VL 36.6, DeepSeek V3.2 0.0, gpt-oss-120b 0.0
Numbers: `web/public/challenge/gridworld-s1000-d1-l6-9b1065f8.json` (from `web/scripts/challenge_stats.py`). Score per level = min(1, optimal/actions) if solved else 0, mean x 100.
Levels 3-5 show a bigger gap (people 56 vs Kimi 13), but visitors would start cold at level 3 while the recorded players had learned levels 1-2, so I kept 1-3. If your insights point to a better game (one with Opus/Gemini runs and human playtests), tell me the id; the page takes `?game=<id>&from=<level>&levels=<n>` and needs only a stats file.


---
**A5 response (DONE, Sat 17:46):**
1. **Filter added & unit-tested:** `analysis/src/analysis/loader.py` (`filter_benchmark_runs`) now drops any run where `player.mode == "challenge"`, `player.purpose == "challenge"`, `meta.mode == "challenge"`, or `meta.purpose == "challenge"` (covered in `test_phase2_h2_bench_and_sampling_export`), so `/challenge` visitor plays never enter the human baseline, `leaderboard.json`, `leaderboard_h2.json`, or `scripts/publish_snapshot.py`.
2. **Demo game pick (`gridworld-s1000-d1-l6-9b1065f8` L1–L3):** Confirmed as the strongest cold-start 3-level pick right now (`82%` human clear / `71.5` score vs Kimi `67.6`, Nemotron `36.6`, text-only `0.0`, with zero cold-start fairness penalty). Once `eval-v1` `s900000` (`d1`, 6 levels, optimal 86) has human + Opus + Gemini + Kimi (`h1` & `h2`) + `verda-ft-qwen3-5-9b` all complete, `?game=gridworld-s900000-d1-l6-33a57ce4&from=1&levels=3` will also be a great judge-facing alternate because all 5 headline players have traces on it!
