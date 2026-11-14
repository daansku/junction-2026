# PLAN.md — Junction 2026, phase 2

**Clock:** written Sat 14.11 16:45 (Helsinki). **We submit Sun 15.11 09:30** (deadline 10:00). About 16.5 working hours left.

**The previous plan** (build the factory, arena, web, first sweeps) is archived in `coordination/PLAN-v1.md`. Its §3 (working rules, ownership, git), §4 (contracts) and §5 (game design rules) **still bind**. This file replaces only its scope, gates and task lists.

**What changes, in one sentence:** we stop building features and turn the project into three claims we can defend in front of the judges: (1) the gap holds when frontier models are run *the way labs benchmark them*; (2) post-training a small model on our games *improves its reasoning on outside benchmarks*, or we show honestly that it does not; (3) people at the venue can feel the gap themselves in a "Can you beat the AI?" demo.

Every agent reads §1–§4 in full, then its own part of §5. Humans read §1, §2 and §6.

---

## 1. Scope

### Must ship
1. **Benchmark-standard harness `h2`** and a frontier rerun on a fixed subset (§3.1). The h1 leaderboard stays as is; h2 is a separate board, never mixed.
2. **Reasoning-benchmark pipeline**: one command evaluates any model (base, SFT, RL checkpoint) on a fixed list of outside reasoning benchmarks plus our held-out games, with identical settings and confidence intervals (§3.2).
3. **Post-training** of a small open model on experience from our games, measured by that pipeline against a control run (§3.3). **This is the most important item in this plan.**
4. **"Can you beat the AI?" demo** for visitors, safe on the public URL (§3.4).
5. **Presentation**: deck, 10-minute demo script, backup video, all numbers claim-checked (§3.5).
6. **Business / real-life value**: a short written exploration, the best two or three ideas on one slide (§3.6).

### Stretch (cut from the bottom up)
1. RL on full multi-turn game episodes (single-turn verifiable tasks are the must-ship RL, §3.3).
2. h2 rerun through the judges' own Harbor + OpenCode harness as a cross-check.
3. Second training iteration driven by the first iteration's failure analysis.
4. Live (not replayed) AI opponent in the demo, using our fine-tuned model.

### Already running — do not disturb
- h1 main sweep on `eval-v1` (A3), Gemma 4 E4B sweep on the Verda host (A4), Nemotron subset (A4). They finish and land on the h1 board.
- Shared server on the Verda CPU VM (`coordination/API_URL`). A2 restarts it only between sweeps.

---

## 2. Gates

| Gate | Time | What must be true |
|---|---|---|
| **H0** | Sat 17:30 | This plan read by all agents. SFT v1 `finetune-eval` result (Qwen3.5-9B base vs `verda-ft-qwen3-5-9b`, h1, `eval-v1`) written in A3's status file, good or bad. Owners of the new folders (§4) have pushed stubs. |
| **H1** | Sat 19:30 | `h2` plays one `eval-v1` game end to end with one Anthropic and one OpenAI-compatible model, reasoning retained across turns, trace marked `harness_version: h2`. Bench pipeline has produced **base-model numbers** for Qwen3.5-9B on the full benchmark list (§3.2). Training-data generators v2 produce valid samples. Demo page playable locally. |
| **H2** | Sat 23:30 | SFT v2 trained and benchmarked against base and control. First RL run (single-turn tasks) running, with at least one checkpoint benchmarked. h2 frontier subset finished or in flight with cost under the approved cap. Demo live on the public URL. Deck v2 with real h1 numbers. |
| **H3** | Sun 05:00 | Best checkpoint chosen by a rule fixed in advance (§3.3), full benchmark run on it with 95% CIs. h2 board built. Business value doc done. |
| **H4** | Sun 07:00 | **Numbers lock.** Only presentation work after this. |
| **H5** | Sun 08:30 | Deck, script, video, README match the locked numbers (claim check passes). **Submit 09:30.** |

---

## 3. Workstreams

### 3.1 Run models the way labs benchmark them (harness `h2`)

**Why:** h1 sends every turn as a fresh single message with rolling notes, no chat history, no retained reasoning, mostly `medium` effort and 16k max output tokens. That is cheap and fair, but a judge can say "you crippled the model". h2 removes that objection. Every choice below must match how providers and ARC Prize report frontier results; look each one up in current provider docs (PLAN-v1 §3.5), do not write it from memory.

**h2 rules (binding for A3; state them on the h2 board):**
1. **Multi-turn conversation.** The model sees its own previous turns, not only a notes field.
2. **Reasoning retained across turns** where the API supports it: Anthropic thinking blocks passed back unchanged; Gemini thought signatures passed back; OpenAI-compatible models: follow each provider's rule for `reasoning_content` (some require it back, some forbid it). Record in the trace which mode each model ran in.
3. **Native tool calling** for actions (`act(action)`), not JSON inside text, where the model supports tools. Invalid or truncated replies are counted in the trace and cost a turn, as in h1.
4. **Highest reasoning effort that providers and public leaderboards normally report** for that model (`max`/`xhigh`/`high`). If that is too expensive on a model, run it at the highest affordable level and label the row with the effort used. Never compare efforts silently.
5. **Generous output limit** (the model's documented maximum, or at least 64k for thinking models) so no reply is cut off by our settings.
6. **Provider-default sampling** (temperature etc.) unless the provider's docs say otherwise for reasoning models.
7. **Context management:** full text history; frames as images for the last N turns (N fixed in the harness, same for all models), older frames dropped; prompt caching on. When the context would overflow, a fixed summarisation step, identical for all models. No hidden information is added; the observation stays pixels only.
8. **Repeats:** ≥ 3 attempts per (model, game) where affordable; report mean and 95% CI. Single-attempt rows are labelled.
9. **Same system prompt idea as h1** (no rule names, no hints), versioned as `prompts/system_h2.md`.

**h2 subset:** 6 `eval-v1` games (2 per difficulty band) + 4 `eval-v2` games, frozen in `arena/sweeps/h2-subset.yaml` before the first run. Models: Claude Opus 5.5, Gemini Pro, Kimi K3.1, one open model, and our best post-trained model (h2 settings apply to it as well). `--dry-run` cost estimate first; anything above the per-sweep cap needs a human OK (§6).

**Done means:** the h2 board shows, per model, score with CI, effort used, reasoning-retention mode, tokens, cost; and the gap to the optimal and human reference is still there (or we report that it closed).

### 3.2 Reasoning-benchmark pipeline (`bench/`)

**Why:** "the model got better at our games" is not interesting; "training on our games made a small model reason better elsewhere" is. The pipeline must make that comparison trustworthy.

**One command:** `make bench MODEL=<id or HF path or vLLM URL> OUT=data/derived/bench/<run>.json`. It serves the model with vLLM on a Verda/Modal GPU, runs every benchmark below with **identical generation settings for every model** (chat template, temperature, max tokens, number of samples, seeds), and writes per-item results so we can do paired comparisons.

**Benchmark list** (check each task's exact name and licence in `lm-evaluation-harness` / the dataset card before using it; drop a benchmark rather than guess):

| Tier | Purpose | Benchmarks |
|---|---|---|
| Near transfer | same skill, new format | our held-out `eval-v1` and `eval-v2` (h1 and h2 harness); Reasoning Gym procedural tasks closest to ours (maze, Sokoban-like, Rush Hour, grid puzzles, ARC-1D); ARC-AGI-1 public eval in text form |
| Logical reasoning | the target | ZebraLogic, Knights and Knaves, BIG-Bench Hard logic subsets (logical_deduction, tracking_shuffled_objects, navigate, web_of_lies), MuSR, FOLIO |
| Regression guard | did we break it? | GSM8K or MATH-500, MMLU-Pro subset, IFEval |

**Statistics:** paired bootstrap over items, 95% CI on every delta; report the effect per benchmark, never only an average. Small benchmarks get several samples per item. Pre-register the comparison (base vs control vs ours) in `bench/PROTOCOL.md` **before** the first trained model is scored.

**Done means:** base Qwen3.5-9B numbers committed by H1; any later model is one command away from a row in `data/derived/bench/`, and A5's page shows deltas with CIs.

### 3.3 Post-training (very important)

**Goal:** improve the logical-reasoning tier of §3.2 for a small open model, using experience from our games, without regressing the guard tier. Base model: **Qwen3.5-9B** (same as SFT v1, so all results compare). If throughput is too low for RL, a 4B sibling for RL experiments only, stated as such.

**Step 0 — read the SFT v1 result first (H0).** SFT v1 trained on optimal action sequences in h1 format (val loss 0.054). Expectation: better on our games, no change on outside reasoning, because it learned actions, not reasoning. Benchmark it in §3.2 anyway: it is a free data point.

**Step 1 — training data v2 (A1 generates, A3 trains).** All from `train-v1`-style seeds, disjoint from every eval set, hold-out rule combinations respected (`engine/src/engine/splits.py`):
- **Reasoning trajectories:** game turns where the target reply contains *explicit reasoning* before the action: what changed in the frame, which hypothesis that supports or kills, what test to run next. Two sources: (a) **rejection sampling** from strong models (Kimi K3.1, Gemini) on train games, keeping only turns from winning, efficient episodes; (b) **templated rationales from engine truth** (the engine knows which rule fired), phrased as discovery, never naming hidden rules the player could not have seen yet.
- **Insight-targeted data:** use A5's failure analysis (`insights.json`, explanations): over-sample the decision points where frontier models fail (acting on premature hypotheses, zero-change wall bumps, resetting too late, missing the newly introduced rule).
- **Auxiliary verifiable tasks** (single turn, cheap, auto-graded by the engine): next-frame prediction after an action; rule induction from a before/after frame pair (multiple choice over effects, not rule names); plan length / "is this level solvable within k moves"; write the full action plan for a level from a text grid (verified by replaying it in the engine).
- **Control set:** an equal-token mix of general open reasoning SFT data with **no game data**, so we can tell "games helped" from "more fine-tuning helped".

**Step 2 — SFT v2** (LoRA, same recipe as v1): three runs — `ctrl` (general data only), `games` (game data only), `mix` (general + game). Benchmark all three. This is the core experiment and must finish by H2.

**Step 3 — RL with verifiable rewards** (GRPO via TRL + vLLM, or an equivalent maintained library; check current docs). Start from the best SFT v2 checkpoint. Rewards come from the engine: correctness on the auxiliary tasks, and the PLAN-v1 §4.6 efficiency score on single-level text-grid episodes. The reward is already exploit-tested; keep it that way (no partial credit a policy can farm). Benchmark a checkpoint every fixed number of steps on a **small dev slice** of §3.2; the full list runs only on the finalist.

**Checkpoint choice rule (fixed now, not after seeing results):** the checkpoint with the best mean on the logical tier dev slice whose regression-guard drop is ≤ 2 points. Final numbers are on the full test sets, reported once.

**Honesty rule:** if no trained model beats `ctrl` on the logical tier with a CI that excludes zero, the pitch says so plainly and shows the in-domain gain and what we learned. That is still a result.

**Compute:** Verda A100s (A3 holds the credits) or Modal. Delete idle GPU instances; log GPU hours and cost in A3's status file.

### 3.4 "Can you beat the AI?" demo

A kiosk-style page for visitors and judges, on the public URL, with no paid model calls.
- New route `/challenge`. Big frame, one short game (3 levels, chosen so humans win more often than frontier models — pick from real h1/h2 data).
- While the visitor plays, the recorded runs of two or three models on the same level advance in step (reuse the ghost-race code), with their stated hypothesis visible.
- End screen: your score vs Opus, Gemini, the fine-tuned 9B and the optimal path; "the AI needed N moves to figure out what you saw in M"; link to the replay.
- Visitor scoreboard (name, score, beat-the-AI yes/no), stored on the server, separate from the human baseline so it never pollutes research data.
- Idle attract mode: replays loop after 60 s without input. QR code on screen so people can play on their phones.
- Touch controls (already exist on Play) and keyboard.
- Stretch: "live AI" toggle that plays our fine-tuned model in real time from the GPU box, only when an operator enables it.

### 3.5 Presentation
- Deck structure (A5 drafts, humans rewrite in their own voice): problem → environment in 30 s → **live demo** → the gap (h1 board, then h2 board: "even run the lab way, they lose") → why failures are meaningful (one replay) → reward integrity (do-nothing / stop-early / exploit attempts) → **post-training result** (base vs ctrl vs ours, with CIs) → business value → ask.
- `docs/DEMO_SCRIPT.md` timed to 10 minutes, with a fallback if the network fails (local `make demo`, recorded video).
- Every number in deck, README and submission traces to a file in `data/derived/` (`python -m analysis check-claims`).

### 3.6 Business and real-life value
`docs/BUSINESS.md`, ≤ 2 pages. For each idea: who pays, what pain it solves, why our factory specifically (procedural, seed-fresh, solvability-proven, pixels-only, reward integrity), what evidence we already have, what we would need. Candidates to assess, not to assume:
- RL environments and training curricula for labs (AfterQuery's own market); "reasoning data that transfers" if §3.3 works.
- Contamination-proof private evals: a fresh, never-published game set per evaluation.
- Pre-deployment testing of agents for adapting to unfamiliar software/UI and limited-resource situations.
- Small on-device models trained for planning (robotics, games, assistants).
- Game industry: solvability-guaranteed level generation and automated QA.
- Cognitive / educational assessment with human baselines (note the ethics and validation burden).
Pick the strongest two or three for the deck, with one sentence each on evidence.

---

## 4. Ownership changes

PLAN-v1 §3.1–3.3 apply (write only where you own, requests in `coordination/requests/`, ship to `main` often, never force-push). New and changed paths:

| Path | Owner | Notes |
|---|---|---|
| `bench/` (new Python package, own `pyproject.toml`) | **A2** | benchmark pipeline, `bench/PROTOCOL.md`, vLLM serve scripts |
| `posttrain/` (new Python package) | **A3** | SFT v2 + RL training code, configs, run logs; `arena/finetune/` stays A3 |
| `engine/src/engine/tasks/` | **A1** | training-data and auxiliary-task generators, RL reward functions (pure, deterministic) |
| `arena/src/arena/` h2 loop, `arena/sweeps/h2-*.yaml`, `prompts/system_h2.md` | A3 | |
| `web/src/features/challenge/` | **A4** | demo page; server endpoints for the visitor board via request to A2 |
| `analysis/` bench + h2 aggregation, `docs/BUSINESS.md`, deck | A5 | |
| `data/derived/bench/` | written only by `bench` | gitignored like the rest of `data/derived/`; published snapshot by A2 |
| `PLAN.md` | humans | |

Add `posttrain/` and `bench/` to `make setup`.

---

## 5. Agent tasks

Times are Helsinki. Task ids continue for status files. If your task is blocked for more than 10 minutes, write it down and take the next one (PLAN-v1 §3.5).

| Window | A1 FORGE | A2 GATEWAY | A3 ARENA | A4 STUDIO | A5 LENS |
|---|---|---|---|---|---|
| **Q0** 16:45–19:30 | data generators v2 + aux tasks | `bench/` pipeline, base numbers | SFT v1 result; h2 harness | `/challenge` page | bench/h2 aggregation spec; deck outline; business doc start |
| **Q1** 19:30–23:30 | RL reward functions, rejection-sampling driver | bench every SFT v2 run; demo endpoints; deploy | SFT v2 ×3; RL run 1; h2 subset sweep | demo polish, attract mode, deploy check | bench page, h2 board; deck v2 |
| **Q2** 23:30–05:00 | data v3 from Q1 failures (stretch) | bench RL checkpoints; snapshot | RL continues; finalist chosen by rule | screenshots, video capture help, QA | findings, business doc done, Q&A prep |
| **Q3** 05:00–09:30 | on call | final snapshot 07:00, keep stack up | final full bench; GPU cleanup | on call, published build | claim check, final deck |

### A1 — FORGE
- **A1-20** `engine/src/engine/tasks/`: generators for next-frame prediction, rule-effect induction (before/after pair, multiple choice), plan length / solvable-in-k, full-plan-from-text-grid. Each sample: prompt, answer, verifier function. Seeds disjoint from all eval collections; respect hold-outs. Determinism test.
- **A1-21** Templated discovery rationales from engine truth for game turns (never naming a rule before the player could have observed its effect). Coordinate the output format with A3's h1/h2 prompt so train == inference.
- **A1-22** RL reward functions: pure functions `(sample, model_output) -> float` for every aux task and for single-level episodes (PLAN-v1 §4.6 score). Unit-test them against obvious exploits (empty answer, repeated answer, over-long plan).
- **A1-23** A small **transfer-probe set** of new games with rule combinations unseen in training *and* in eval-v1 (fresh seeds), for the near-transfer tier.
- Engine and frozen collections stay frozen; bug fixes only.

### A2 — GATEWAY
- **A2-20** `bench/`: vLLM serve + `lm-evaluation-harness` runner (+ Reasoning Gym / ZebraLogic / K&K loaders where not in lm-eval), fixed generation config file, per-item output, paired bootstrap. `make bench`. Write `bench/PROTOCOL.md` with A3 and A5 and commit it before any trained model is scored.
- **A2-21** Base Qwen3.5-9B numbers by H1 (GPU from A3's Verda credits or Modal; ask A3 for access).
- **A2-22** Visitor-board endpoints for `/challenge` (`POST /challenge/score`, `GET /challenge/board`), stored apart from research runs, allowed in published mode, rate-limited, name length capped, no free text other than the name.
- **A2-23** Deploy the demo on the public URL; phone test; `data/published/` snapshot at H2 and at 07:00.

### A3 — ARENA
- **A3-20** (H0) Finish `finetune-eval`, write base vs SFT v1 numbers in the status file, then delete or park the 2×A100 instance.
- **A3-21** h2 harness per §3.1 (Anthropic first, then OpenAI-compatible, then Gemini). `harness_version: h2`. Test on one game per provider.
- **A3-22** `h2-subset.yaml` frozen, `--dry-run` estimate, request human approval if over cap, then run.
- **A3-23** `posttrain/`: SFT v2 `ctrl` / `games` / `mix` (same LoRA recipe, same token count), handed to A2's bench.
- **A3-24** Rejection-sampling run on train games with Kimi/Gemini (cost estimate first) feeding A1-21's data.
- **A3-25** RL (GRPO) on A1's tasks from the best SFT v2 checkpoint; checkpoints to bench on the dev slice; finalist by the §3.3 rule.
- **A3-26** Register the finalist in `models.yaml` (`tier: finetuned`) and run it on h1 and h2 so it appears on both boards.

### A4 — STUDIO
- **A4-20** `/challenge` per §3.4: game choice from real data (with A5), synced model ghosts, end screen, visitor board (mock until A2-22 lands), attract mode, QR code, touch + keyboard, published-mode safe.
- **A4-21** Projector and phone QA of `/challenge`; one-click "reset kiosk" for the booth.
- **A4-22** Screenshot and screen-recording set for the deck and backup video.
- Keep supporting A5 on the pages A5 took over; `/challenge` must not change their files (request if needed).

### A5 — LENS
- **A5-20** Analysis: h2 aggregation (separate board, effort and retention mode as columns); bench aggregation (deltas vs base and vs `ctrl`, CIs) → `data/derived/bench_summary.json`; a bench/post-training page or section.
- **A5-21** Export failure insights in a form A1/A3 can sample from (decision-point type, game, level, step) for insight-targeted data.
- **A5-22** `docs/BUSINESS.md` per §3.6.
- **A5-23** Deck v2 (H2) and final (H5), `docs/DEMO_SCRIPT.md` with the live demo and network fallback, `docs/QA_PREP.md` updated with "did you cripple the models?" and "is the transfer real?" answers, claim check.

---

## 6. Humans — decisions and tasks

| When | Task | Why an agent can't |
|---|---|---|
| **now** | Read §3.1 rule 4 and decide the effort policy for expensive models: `max` on a smaller subset, or `high` on the full h2 subset. Record in `DECISIONS.md`. | money, judgment |
| **by 18:30** | Approve the h2 subset cost estimate (A3 posts it) and a GPU-hour budget for SFT v2 + RL (suggest: total cap in `DECISIONS.md`). | money |
| **by 19:00** | Approve `bench/PROTOCOL.md` (benchmark list, checkpoint rule). After this nobody changes the list. | keeps the result honest |
| **Q1** | Playtest `/challenge`; pick the demo game if the data-driven pick is not fun. | taste |
| **H2 23:30** | Review SFT v2 results; decide whether RL continues overnight. | risk call |
| **Q2** | Read `docs/BUSINESS.md`, pick the 2–3 ideas for the deck; rewrite the deck in your own words; record demo video + backup screen recording. | your voice |
| **07:00** | Numbers lock. | |
| **08:00–09:30** | Final check of site, deck, numbers, README one-command eval. **Submit 09:30.** | platform login |
| **after** | Peer review; rehearse the pitch twice, timed; run the booth demo. | in person |

---

## 7. If we fall behind

- Cut in this order: live-AI demo toggle → Harbor/OpenCode h2 cross-check → multi-turn RL → second data iteration → RL entirely (SFT v2 three-way comparison is the minimum post-training result) → h2 repeats (run 1 attempt, label it).
- Never cut: the `ctrl` comparison and CIs in post-training, separate h1/h2 boards, the demo, the claim check, the recorded video.
- Bench pipeline not producing base numbers by 20:30 → A5 helps A2; drop the benchmarks that are not running yet and keep the logical tier.
- GPU unavailable for more than 30 minutes → switch provider (Verda ↔ Modal), log it, keep going.
- h2 over budget → fewer games, never lower effort silently.
