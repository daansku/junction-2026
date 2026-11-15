# Game Factory — Failure Patterns, New Games, and Transfer Results (`docs/story-deck/`)

> **Interactive HTML Presentation:** Open [`docs/story-deck/index.html`](index.html) directly in any browser (or visit `/story-deck/` when served).
> - Press **`P`** (or click **Present Fullscreen**) for 16:9 presentation mode (left/right arrow keys or `Space` to advance).
> - Press **`N`** (or click **Speaker Notes**) to toggle presenter notes beneath every slide.

---

## Narrative Design: From One Failure to Thousands of Games

The deck follows the video: one failed run becomes a pattern across many fresh games. It then explains how the games work, what model tests show, how failures are diagnosed, how the score is protected, and what training and transfer results we have so far.

| Slide | Story & Business Beat | AfterQuery Requirement Fulfilled | Timing |
|---:|---|---|---:|
| **01** | **Break One, Break Many:** One model walks into the same wall 11 times. Across thousands of fresh games, failures form patterns that show what AI still cannot do. | Introduces the factory's purpose | `0:50` |
| **02** | **Business Case — Who Pays & Why Now:** 3 markets need this: field robots, private business AI, and AI test teams. Game Factory generates and checks each new puzzle in under 2 seconds; custom tests take design and engineering work. | Contamination-resistant procedural scaling (`0%` leak) | `0:50` |
| **03** | **New Games by Seed:** Every seed creates a new `64×64` game with 16 colours and six actions. Each level hides a rule. Search confirms levels can be solved. | **Craft & Environment (`15 / 15 pts`):** `1,000/1,000` BFS solvable, `100%` `gridforce` forced discovery, `4.0` `gridbranch` loops, `<2%` random walk | `0:55` |
| **04** | **Live Experience (`/challenge`):** Scan the code to play a puzzle with no instructions, then compare your run with recorded AI play on the same board. | Live demonstration | `1:30` |
| **05** | **The Gap:** On fresh games, people win more often than the AI. With the lab setup, Gemini 4 finishes all four games but needs more moves than the optimal solver. Most models finish none. | **The Gap (`30 / 30 pts`):** Human-vs-AI performance gap and optimal reference | `0:55` |
| **06** | **Solution Step 3 — `/insights` Automated Reasoning Forensics:** Truth-Diffed Reasoning Auditor (`explain.py`) slices ±2-step inflection windows across `319` failed levels and diffs verbatim `<think>` CoT/notes against engine truth into a 5-stage bottleneck funnel (`h1 to h2` board misreads `40% to 0%`; `50%` of 194 decision errors are zero-effect gate loops; `44%` reset too late). | **Meaningful Difficulty (`30 / 30 pts`, Part 1):** Actionable failure taxonomy separating harness bugs from true reasoning limits | `1:05` |
| **07** | **`/insights` Deep Dive — The 54.4% "Knowing–Doing Gap":** Across `117 / 215` failed hidden-rule levels (`64%` in `h2`), `/insights` proves the model **stated the exact mechanic in its CoT** yet failed multi-step spatial execution — with 1-click `[ X-Ray @step to ]` into `/replay`. | **Meaningful Difficulty (`30 / 30 pts`, Part 2):** Verbatim quote-vs-reality evidence proving prompting isn't enough | `1:00` |
| **08** | **Reward Integrity:** A level scores for efficient completion. Doing nothing scores zero, stopping early earns credit only for completed levels, and resets do not erase moves. The grader runs in a separate container. | **Reward Integrity (`25 / 25 pts`):** Protected scoring with tested cheat attempts | `0:50` |
| **09** | **Training on Games:** Training Qwen3.5-9B on single moves with reasoning enabled raised its score from `58.9%` to `64.0%` after 30 steps on 175 math questions. | **Stretch Goal & Tiebreaker:** Post-training a compact open model | `1:05` |
| **10** | **Rover Transfer Test:** On 100 simulated missions with scrambled controls, Qwen3.5-4B went from `39` completed missions before training to `44` after. The difference was not statistically significant (`p = 0.42`). | Checks whether game training transfers beyond the games | `0:40` |
| **11** | **Business Model:** Failure reports, training games, and private tests for each customer. | Sustainable B2B model based on fresh, verified games | `0:45` |
| **12** | **Try the AI:** Reproduce results with `make setup` and `harbor run`, then try to beat the AI yourself. | **Reproducibility Gate:** Run the evaluation in one command | `0:35` |

**Total Target Run Time:** `~11:00` (includes the rover result and fits a 10–12 min pitch with a short live demo).

---

## Verified Data Sources

Every metric on the slides is pulled directly from live repository artifacts and production endpoints:

1. **Benchmark & Gap (`Slide 05`):**
   - `https://65.108.33.107.compute.verda.run/api/derived/leaderboard.json` (`eval-v2` `h1`: Optimal `100%` `20/20`, Humans `73.9%` `17/23` games / `91.8%` levels, Gemini 4 Carbon `44.4%` `8/18`, Gemini 4 Argon `10.0%` `3/30`, Kimi K3.1 `0%` `0/3`, Gemini Flash `0%` `0/20`, Claude Sonnet 5.5 `0%` `0/1`, `9B`/`4B` open models `<3%` levels).
   - `https://65.108.33.107.compute.verda.run/api/derived/leaderboard_h2.json` (`eval-v2` 4-game subset `s5000..s5003`: `Gemini 4` `h2`/`h2b` `100%`, `DeepSeek V3.2` `25%`, `Gemini 3.1 Pro` `0%`, `Kimi K2.5` `0%`).
2. **`/insights` Reasoning Forensics (`Slides 06–07`):**
   - `https://65.108.33.107.compute.verda.run/api/derived/explanations.json` (`319` audited failed levels: `115` `perception` `36.1%`, `37` `rule_induction` `11.6%`, `55` `belief_updating` `17.2%`, `102` `spatial_planning` `32.0%`, `10` `budget_management` `3.1%`; `h1 to h2` `perception` `40.2% to 0.0%`, `spatial_planning` `28.7% to 60.6%`; **Knowing–Doing Gap = `54.42%` (`117 / 215` non-Tier-0; `63.64%` = `21 / 33` in `h2`)**).
   - `https://65.108.33.107.compute.verda.run/api/derived/decision_points.json` (`194` failure decision points: `50%` zero-effect action loops, `44%` late resets, `6%` rule misses).
3. **`Qwen3.5-9B` Post-Training (`Slide 09`):**
   - `posttrain/grpo.py`, `bench/PROTOCOL.md` (v3), `https://65.108.33.107.compute.verda.run/api/derived/bench_summary.json`, and `coordination/requests/A3-to-A2-B200-thinking-rl.md` (`SFT v1` `4/180` levels = `2.2%`; no-think collapse `0.758 to 0.44`; Thinking-On GRPO `95–100%` closed `</think>`; dev-slice `MATH` `58.9% to 64.0%` on `think-games-h2-s30` and `63.4%` on `think-gridbranch-s10`, `MMLU-Health` `72.0% to 76.0% / 80.0%`, `GSM8K` `96.0%`, `MedQA` `80.0%`).
4. **Engine Verification & Harbor Red-Team (`Slides 03 & 08`):**
   - `coordination/A7_AUDIT.md` (`1,000 / 1,000` fuzzed seeds solvable, `100%` `gridforce` forced-discovery pass, `4.0` `gridbranch` loops/level, `<2%` random walk, `143` engine unit tests).
   - `coordination/JUDGING.md` (`harbor==0.26.0`, Oracle `1.000`, Nop `0.000`, Stop-early `0.167` / `0.125`, OpenCode + Nemotron `0.067`, and Red-Team Rows 1–10 all `0.000`).
5. **Commercial Model (`Slides 02 & 11`):**
   - [`docs/BUSINESS.md`](../BUSINESS.md).
6. **Rover Transfer Test (`Slide 10`):**
   - [`video/rover.json`](../../video/rover.json) (39/100 before training, 44/100 after, paired test `p = 0.42`; simulator, not physical hardware).
