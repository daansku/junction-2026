# Game Factory — Coal Mine Story, Business Case, and Challenge Deck (`docs/story-deck/`)

> **Interactive HTML Presentation:** Open [`docs/story-deck/index.html`](index.html) directly in any browser (or visit `/story-deck/` when served).
> - Press **`P`** (or click **Present Fullscreen**) for 16:9 presentation mode (left/right arrow keys or `Space` to advance).
> - Press **`N`** (or click **Speaker Notes**) to toggle presenter notes beneath every slide.

---

## Narrative Design: One Continuous Customer Story + Full Challenge Rubric Coverage

Every slide advances a single concrete B2B story (**Unit-7**, an autonomous inspection robot 600m inside a collapsed coal mine running an offline `9B` edge model) while explicitly calling out **who pays**, **how `/insights` diagnoses failures**, **how `Qwen3.5-9B` post-training fixes the bottleneck**, and **which AfterQuery Challenge requirement (100/100 pts + Stretch/Tiebreaker) each step fulfills**:

| Slide | Story & Business Beat | AfterQuery Requirement Fulfilled | Timing |
|---:|---|---|---:|
| **01** | **The Crisis (600m Underground):** Unit-7 (`9B` local model, zero Wi-Fi/5G, 40-min battery) hits a corroded ventilation airlock whose pressure-plate & gate wiring shifted after a rockfall. Current local models ram the locked gate 50 times (`€120k` robot lost). | Sets up unseen causal discovery under strict action budget | `0:50` |
| **02** | **Business Case — Who Pays & Why Now:** 3 markets need this: field robots, private business AI, and AI test teams. Game Factory generates and checks each new puzzle in under 2 seconds; custom tests take design and engineering work. | Contamination-resistant procedural scaling (`0%` leak) | `0:50` |
| **03** | **Solution Step 1 — Digital Twin of Unseen Mechanics:** Procedural factory composes `21` physical & causal mechanics (`2,035` training worlds + `60` frozen held-out test worlds) with 4-gate mathematical verification (`<2s` on CPU). | **Craft & Environment (`15 / 15 pts`):** `1,000/1,000` BFS solvable, `100%` `gridforce` forced discovery, `4.0` `gridbranch` loops, `<2%` random walk | `0:55` |
| **04** | **Live Experience (`/challenge`):** Judges & engineering buyers scan QR to step into Unit-7's sensors with zero text hints and race recorded AI replays side-by-side in 60 seconds. | **Demonstrated Reference Run** & instant sales wedge | `1:30` |
| **05** | **Solution Step 2 — Stress-Testing Before Deployment:** On `eval-v2` (30 unseen 8-level games), first-try humans win **74%** (`17/23`), cloud `h1` agents win `44%` / `10%` / `0%`, and `9B` edge models solve `<3%` of levels. Multi-turn cloud `h2` (`$15/game`) lifts top `Gemini 4` to `100%` (proving 100% fair solvability) while `Gemini Pro` & `Kimi` win `0/4` — and cloud doesn't exist underground. | **The Gap (`30 / 30 pts`):** Large, statistically clean human-vs-AI frontier & edge gap + proven solvability | `0:55` |
| **06** | **Solution Step 3 — `/insights` Automated Reasoning Forensics:** Truth-Diffed Reasoning Auditor (`explain.py`) slices ±2-step inflection windows across `319` failed levels and diffs verbatim `<think>` CoT/notes against engine truth into a 5-stage bottleneck funnel (`h1 to h2` board misreads `40% to 0%`; `50%` of 194 decision errors are zero-effect gate loops; `44%` reset too late). | **Meaningful Difficulty (`30 / 30 pts`, Part 1):** Actionable failure taxonomy separating harness bugs from true reasoning limits | `1:05` |
| **07** | **`/insights` Deep Dive — The 54.4% "Knowing–Doing Gap":** Across `117 / 215` failed hidden-rule levels (`64%` in `h2`), `/insights` proves the model **stated the exact mechanic in its CoT** yet failed multi-step spatial execution — with 1-click `[ X-Ray @step to ]` into `/replay`. | **Meaningful Difficulty (`30 / 30 pts`, Part 2):** Verbatim quote-vs-reality evidence proving prompting isn't enough | `1:00` |
| **08** | **Solution Step 4 — Upgrading Unit-7 via `Qwen3.5-9B` Post-Training:** Factory exports failure-targeted tasks (`game_turn`, `rule_effect`, `blocked_moves`). Shows why naive `SFT v1` (`4/180 = 2.2%`) and stripping `<think>` (`0.758 to 0.44`) failed, and how **Thinking-On GRPO (`RL v2` on B200)** keeps `95–100%` `</think>` closure while lifting dev-slice **MATH `58.9% to 64.0% (+5.1 pp)`** & **MMLU-Health `72% to 76–80%`** under `PROTOCOL v3`. | **Stretch Goal & Tiebreaker:** Verifiable RL post-training for compact `<10B` open-weight models + out-of-distribution transfer | `1:05` |
| **09** | **Solution Step 5 — Preventing RL Reward Hacking:** Harbor (`0.26.0`) + isolated MCP sidecar verifier: Oracle = `1.000`, Nop = `0.000`, Stop-early = `0.167`/`0.125`, OpenCode+Nemotron = `0.067`, and **`10 / 10` container + network red-team exploits = `0.000`**. | **Reward Integrity (`25 / 25 pts`):** Tamper-proof continuous efficiency verifier ready for 15-min live exploit hunt | `0:50` |
| **10** | **Commercial Model — Diagnose to Train to Certify:** Tier 1 `/insights` Readiness SaaS (`€2,000/mo`), Tier 2 Custom Edge RL & Lab Gym (`€15k–€50k`), Tier 3 Zero-Leak Harbor Audits (`€5,000`), at **99%+ software gross margin**. | Sustainable B2B SaaS + RL Gym go-to-market aligned with AfterQuery's ecosystem | `0:45` |
| **11** | **Complete Scorecard & 1-Command Reproducibility:** Exact `make setup` + `harbor run` commands, live routes (`/insights`, `/challenge`, `/replay`), and `100 / 100 + Tiebreaker` summary table. | **Reproducibility Gate:** Clone-to-eval in one command | `0:35` |

**Total Target Run Time:** `~10:20` (fits cleanly inside a 10–12 min pitch + live `/challenge` & `/insights` demo + Q&A).

---

## Verified Data Sources

Every metric on the slides is pulled directly from live repository artifacts and production endpoints:

1. **Benchmark & Gap (`Slide 05`):**
   - `https://65.108.33.107.compute.verda.run/api/derived/leaderboard.json` (`eval-v2` `h1`: Optimal `100%` `20/20`, Humans `73.9%` `17/23` games / `91.8%` levels, Gemini 4 Carbon `44.4%` `8/18`, Gemini 4 Argon `10.0%` `3/30`, Kimi K3.1 `0%` `0/3`, Gemini Flash `0%` `0/20`, Claude Sonnet 5.5 `0%` `0/1`, `9B`/`4B` open models `<3%` levels).
   - `https://65.108.33.107.compute.verda.run/api/derived/leaderboard_h2.json` (`eval-v2` 4-game subset `s5000..s5003`: `Gemini 4` `h2`/`h2b` `100%`, `DeepSeek V3.2` `25%`, `Gemini 3.1 Pro` `0%`, `Kimi K2.5` `0%`).
2. **`/insights` Reasoning Forensics (`Slides 06–07`):**
   - `https://65.108.33.107.compute.verda.run/api/derived/explanations.json` (`319` audited failed levels: `115` `perception` `36.1%`, `37` `rule_induction` `11.6%`, `55` `belief_updating` `17.2%`, `102` `spatial_planning` `32.0%`, `10` `budget_management` `3.1%`; `h1 to h2` `perception` `40.2% to 0.0%`, `spatial_planning` `28.7% to 60.6%`; **Knowing–Doing Gap = `54.42%` (`117 / 215` non-Tier-0; `63.64%` = `21 / 33` in `h2`)**).
   - `https://65.108.33.107.compute.verda.run/api/derived/decision_points.json` (`194` failure decision points: `50%` zero-effect action loops, `44%` late resets, `6%` rule misses).
3. **`Qwen3.5-9B` Post-Training (`Slide 08`):**
   - `posttrain/grpo.py`, `bench/PROTOCOL.md` (v3), `https://65.108.33.107.compute.verda.run/api/derived/bench_summary.json`, and `coordination/requests/A3-to-A2-B200-thinking-rl.md` (`SFT v1` `4/180` levels = `2.2%`; no-think collapse `0.758 to 0.44`; Thinking-On GRPO `95–100%` closed `</think>`; dev-slice `MATH` `58.9% to 64.0%` on `think-games-h2-s30` and `63.4%` on `think-gridbranch-s10`, `MMLU-Health` `72.0% to 76.0% / 80.0%`, `GSM8K` `96.0%`, `MedQA` `80.0%`).
4. **Engine Verification & Harbor Red-Team (`Slides 03 & 09`):**
   - `coordination/A7_AUDIT.md` (`1,000 / 1,000` fuzzed seeds solvable, `100%` `gridforce` forced-discovery pass, `4.0` `gridbranch` loops/level, `<2%` random walk, `143` engine unit tests).
   - `coordination/JUDGING.md` (`harbor==0.26.0`, Oracle `1.000`, Nop `0.000`, Stop-early `0.167` / `0.125`, OpenCode + Nemotron `0.067`, and Red-Team Rows 1–10 all `0.000`).
5. **Commercial Model (`Slides 02 & 10`):**
   - [`docs/BUSINESS.md`](../BUSINESS.md).
