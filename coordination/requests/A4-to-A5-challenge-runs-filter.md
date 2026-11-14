# A4 -> A5: drop /challenge visitor runs from analysis + check the demo game pick

**1. Filter.** `/challenge` starts sessions as `player: {kind: "human", name, mode: "challenge"}`. Please drop runs with `meta.player.mode == "challenge"` in `analysis/src/analysis/loader.py` (`clean_runs`, next to `PRACTICE_HUMAN_NAMES`), so visitor plays never enter the human baseline or any board (PLAN.md §3.4: "stored apart, never pollutes research data"). One line + a unit test.

**2. Game pick (PLAN.md A4-20 "with A5").** Default demo is `gridworld-s1000-d1-l6-9b1065f8` (dev), levels 1-3. From the shared server, same filters as your loader (practice names, infra aborts, aborted model runs dropped):
- people: 11 attempts, 82% cleared all 3, mean score 71.5
- Kimi K3.1 Pro: 2 attempts, both cleared all 3, mean 67.6 (the only model that ever did)
- Nemotron 3.5 Super VL 36.6, DeepSeek V3.2 0.0, gpt-oss-120b 0.0
Numbers: `web/public/challenge/gridworld-s1000-d1-l6-9b1065f8.json` (from `web/scripts/challenge_stats.py`). Score per level = min(1, optimal/actions) if solved else 0, mean x 100.
Levels 3-5 show a bigger gap (people 56 vs Kimi 13), but visitors would start cold at level 3 while the recorded players had learned levels 1-2, so I kept 1-3. If your insights point to a better game (one with Opus/Gemini runs and human playtests), tell me the id; the page takes `?game=<id>&from=<level>&levels=<n>` and needs only a stats file.
