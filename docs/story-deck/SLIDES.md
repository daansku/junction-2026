# VERITAS · Game Factory — Story × Rubric Pitch Deck (`docs/story-deck/`)

Open `docs/story-deck/index.html` directly in any browser:
- **`P`** (or click **Present Fullscreen (P)**) enters 16:9 fullscreen presentation mode (`←` / `→` / `Space` or click right/left screen thirds).
- **`N`** (or click **Speaker Notes (N)**) toggles slide-by-slide speaker notes in the contact-sheet view.
- **`Esc`** exits fullscreen presentation mode.

> **Why this deck exists alongside `docs/deck/`:** Built to weave **real-world use-case storytelling + commercial value** (offline edge robotics, enterprise agent readiness, contamination-proof lab evals, and RL curricula) **simultaneously** with **100% of AfterQuery's Challenge Rubric (`100 pts + Tiebreaker`)** on every single slide — rather than leaving business value to a single slide at the end. (`docs/deck/` owned by A1 remains untouched.)

---

## 10-Minute Story × Rubric Arc

| Slide | Story / Business Beat | AfterQuery Rubric Beat | Target Time |
|---|---|---|---|
| **01 · When the Manual Runs Out** | Offline mine/subsea robots on a battery budget & enterprise agents facing undocumented UI changes fail when rules shift without a prompt. | Introduces `64×64` pixel-only RL environment (`21` rules, `<2s` generation, `1,280+` runs). | `0:45` |
| **02 · Why Static Evals Leak & Gyms Don't Scale** | AI labs & agent builders lose millions to leaked benchmarks and `$1k–$10k` hand-authored tasks. | **Craft (15 pts):** 4-gate CPU verifier (`1,000/1,000` BFS solvable, `100%` `gridforce` rule necessity, `4.0` `gridbranch` loops, `<2%` random walk). | `1:00` |
| **03 · Live Demo (`/challenge`)** | Experiential buyer hook + human discovery trace flywheel. | **Demonstrated Reference Run:** Judges scan QR & race recorded frontier models in 60s. | `1:45` |
| **04 · Product #1: Private Evals × The Gap** | Fresh one-time seed range (`s950000+`) per enterprise/safety contract — zero training leakage. | **The Gap (30 pts):** On unseen `eval-v2` (8 levels, 3 held-out rules), Humans win **`74%`** (`17/23`) vs `44%` Carbon, `10%` Argon, `0%` Kimi/Flash/Sonnet, `<3%` `<10B` edge models. | `1:00` |
| **05 · Cloud Lab (`h2`) vs. Edge Constraints** | Cloud `h2` costs `$5–$18/game` and requires internet — impossible for an offline `9B` robot on a Jetson Orin. | **Fairness & Harness Ablation:** Top `Gemini 4` reaches `100%` on 4-game `h2`/`h2b` subset (proving **zero unfair tricks**), while `Gemini Pro` & `Kimi` still win `0/4`. | `0:50` |
| **06 · Product #2: Readiness Audit × Why They Fail** | Catches battery-draining jammed-valve loops and runaway RPA clicks before production launch. | **Meaningful Difficulty (30 pts):** **`54.4%` Knowing–Doing Gap** (`117/215` stated the rule in CoT yet failed spatial rollout) + `50%` zero-effect loops + `44%` late resets (`/insights` + `/replay` X-Ray). | `1:00` |
| **07 · Product #3: Anti-Cheat RL Verifier** | Drop-in tamper-proof MCP sidecar for AfterQuery & lab RL pipelines. | **Reward Integrity (25 pts):** Oracle `1.000`, Do-nothing `0.000`, Stop-early `0.167`/`0.125`, Nemotron `0.067`, and **`10 / 10` container + network red-team exploits = `0.000`**. | `0:50` |
| **08 · Edge AI Case Study (`Qwen3.5-9B`)** | Distilling reasoning into a `9B` edge-sized planner for offline environments. | **Stretch Goal / Tiebreaker:** Pre-registered `PROTOCOL v3` — `SFT v1` (`4/180` levels) & no-think collapse (`0.758 → 0.44`) vs **Thinking-On GRPO (`RL v2`)** (`+5.1 pp` MATH dev-slice `58.9% → 64.0%`, `95–100%` `</think>` closure). | `1:00` |
| **09 · One Engine, Three Revenue Streams** | Unit economics (`~1 CPU-sec` = `$0.0001/world`) powering RL Gym, Private Evals, and Pre-Launch Audits. | Synthesizes why procedural verification unlocks both training and ungameable testing. | `0:45` |
| **10 · 1-Command Reproducibility & Exploit Invite** | Live URLs (`/challenge`, `/insights`, `/replay`) + commercial readiness. | **Craft (15 pts) + 100/100 Scorecard:** Exact `harbor run` commands + invitation to the 15-minute exploit hunt. | `0:45` |

---

## Verified Data Sources

- **Engine & 4-Gate Verification:** `engine/src/engine/` (`0.6.0`, `143` unit tests, `1,000/1,000` fuzz), `coordination/A7_AUDIT.md` (`gridforce` `112/112 = 100%`, `gridbranch` `4.0` loops/level).
- **Live `eval-v2` `h1` & `h2` Boards:** `https://65.108.33.107.compute.verda.run/api/derived/leaderboard.json` & `leaderboard_h2.json` (`1,280+` recorded runs, finished-only filter, completion-first ranking).
- **Truth-Diffed Reasoning Forensics (`319` failed levels, `54.4%` Knowing–Doing Gap) & `194` Decision Points:** `explanations.json` & `decision_points.json`.
- **Harbor `0.26.0` + 10 Red-Team Attacks:** `coordination/JUDGING.md` (Results & Red-Team rows 1–10), `harbor/eval-v1/`, `harbor/eval-v2/`.
- **Post-Training (`Qwen3.5-9B`):** `bench/PROTOCOL.md` (v3), `coordination/requests/A3-to-A2-B200-thinking-rl.md`, `bench_summary.json` (`think-games-h2-s30`, `think-gridbranch-s10`).
