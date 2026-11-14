# Decisions (humans only)

- Project name:
- Shared server host: A2 machine + tunnel; since Sat 15:15 a dedicated Verda CPU VM (`coordination/API_URL`)
- Spend cap per sweep: $20
- Total model budget: $300 (raised Sat 13:55; about $5 spent before)
- Challenge / track:
- Final deploy host:

## Main sweep on eval-v1 (approved Sat 13:55, recorded by A4 for the human)
- Approved up to **$210** for the sweeps below, above the $20 per-sweep cap: A3 runs them with `--approve-cost`. Details and the per-sweep breakdown: `coordination/requests/A4-to-A3-main-sweep-approved.md`.
- All 30 games x 3 attempts: Claude Haiku 5.5, Gemini Flash, DeepSeek V3.2 (featherless), baselines.
- Subsets, 1 attempt: Kimi K3.1 on 10 games, Claude Sonnet 5.5 on 10 games, Claude Opus 5.5 on 5 games. Marked as subsets on the leaderboard.
- Nemotron is not in the eval-v1 sweep (endpoint takes ~30 s per request, one game ~3.3 h); it is reported from the overnight dev run only.
- Update Sat 14:45 (human): Nemotron runs a small eval-v1 subset after all, from A4's machine: `arena/sweeps/main-subset-nemotron.yaml`, first 3 games x 1, one request at a time, 4 h wall cap per game, Verda credits. A3: don't run Nemotron elsewhere at the same time (the endpoint only queues).
- Wall cap 3 h per run, `max_actions` 400 is the budget, so scores don't measure API latency.
- **Update Sat 14:10 (ignacio, recorded by A3): Claude rows changed.** The Anthropic key only had ~EUR 20, so Haiku 30x3 and Sonnet 10 were dropped; Opus 5.5 (medium) on 2 games instead. The 14:16 host crash killed both Opus runs; Opus was rerun on the hard d3 game only (s900002, $9 cap): 5/6 levels, 290 actions, score 0.506. About $7 left on the key.
- **Update Sat 14:30 (A3): DeepSeek V3.2 on the first 10 games x 1 only** (Featherless runs it at ~14 s/action with 2 parallel slots; 30x3 would take ~70 h).

## Improvement plan (Sat 14:10, Anssi; recorded by A2 for the human)
- New mechanics, LLM failure explanations and the "Epistemic Arena" UI upgrade: plan and split in `coordination/COORDINATION.md`.
- **A5 leads the UI upgrade.** For this work A5 takes over `web/src/lib/FrameCanvas.tsx`, `features/play/PlayPage.tsx`, `features/replay/ReplayPage.tsx` and `features/overview/OverviewPage.tsx` from A4; A4 supports and reviews.

## Phase 2 (PLAN.md written Sat 16:45)
- **h2 harness effort and budget (Sat 17:40, ignacio, recorded by A3):** Kimi K3.1 (effort max, Verda credits) and Gemini 3.1 Pro (effort high) run once on the frozen 10-game h2 subset (`arena/sweeps/h2-subset-v1.yaml` 6 eval-v1 games + `h2-subset-v2.yaml` 4 eval-v2 games). Gemini Pro approved at ~$145, hard cap $18 per run (worst case $180). Opus 5.5 on h2 (~$227 for the subset) only if the Anthropic key is topped up. Claude Haiku 5.5 (high) played one h2 game for the H1 gate (~$0.75 total).
- **Fine-tune benchmark list (Sat 17:55, ignacio, recorded by A3):** Daniel's `FT_BENCHMARKS.md` is final (replaces the list in the `bench/PROTOCOL.md` v1 draft): BBH all 27 (3-shot CoT), MATH (0-shot CoT), GSM8K (8-shot CoT), MedQA-USMLE 4-option (0-shot), MMLU-Pro health and law (5-shot); headline = unweighted mean of those six; MMLU-Pro history = negative control; five pre-declared BBH tasks reported separately; greedy decoding; 1,000-item fixed-seed subsample for intermediate checkpoints.
- **GPU (Sat 15:00 / 17:50):** the 2x A100 Verda box (`95.216.229.250`) is the only GPU instance; it stays up until the end (~$4.77/h). GPU 0 = A2 bench, GPU 1 = A3 (comparison serving, then SFT v2 / RL).
- **Cost note (Sat 17:15, A3):** Gemini costs logged before 17:15 are ~3.6x too low (thinking tokens were not counted); fixed for new runs. Real model spend so far is therefore higher than the traces show: expect Gemini Flash h1 main ~$125 real.
- **eval-v2 frontier runs (Sat 18:20, ignacio, recorded by A3):** Kimi K3.1 (credits) and Gemini Flash (medium, ~$45) on all 30 eval-v2 games x1, h1, same budgets as the eval-v1 main sweep, plus baselines (`arena/sweeps/eval-v2-frontier.yaml`). Note: total committed model spend is now ~$360 vs the $300 cap (Gemini costs were undercounted ~3.6x before 17:15).
- **Extra GPU (Sat 18:20, ignacio):** 1x H100 80 GB at `31.22.104.125` for A3 (SFT v2 / RL), "use it as you please".

## Bench (Sat 18:00 and 20:15, Anssi; recorded by A2 for the human)
- Fine-tune benchmark list = `FT_BENCHMARKS.md` (also decided 17:55 by ignacio), implemented in `bench/` as the primary suite; reasoning-gym kept as a secondary tier.
- Decoding: Qwen3.5 model-card sampling (temperature 1.0, top_p 0.95, top_k 20, presence_penalty 1.5), not greedy.
- Suite size: fixed subsample per model (~2,250 generative items + full MedQA; BBH 50/task, MATH 50/subject, GSM8K 250, MMLU-Pro health/law/history 100 each), same items for every model. Full suite was ~13 h per model. Protocol: `bench/PROTOCOL.md` v3.
- **Gemini credits are unlimited (Sat 19:25, ignacio):** the $300 model budget no longer binds Gemini. Main sweep keeps 3 attempts; Gemini runs get cost caps high enough never to cut a run short (eval-v2 Gemini Flash rerun at $15/run, `arena/sweeps/eval-v2-gemini*.yaml`; the 7 eval-v2 runs capped at $2 are redone as attempt 1). The cap still applies to Anthropic and other paid APIs.
- **Gemini 4 Argon + Carbon on eval-v2 (Sat 19:28, human, recorded by A4):** all 30 eval-v2 games x1 each, h1, medium, 400 actions, $15/run cap (`arena/sweeps/eval-v2-gemini4.yaml`). Approved with `--approve-cost 340` (dry-run $336; expected ~$210 real at ~$0.01/action). Gemini credits, so outside the $300 model budget (19:25 decision). Argon's earlier eval-v2 runs cut at $4 (`main-subset-argon-v2`, `challenge-argon-v2`) are superseded by these.

## Forced-interaction generator, A7 (Sat ~19:45, Anssi; recorded by A7)
- **Newest rule (hard requirement):** on every level that introduces a rule, the optimal path must trigger it, and the best plan that never triggers it must be impossible or >= 2x the optimal length (avoider scores <= 0.5 on that level).
- **Older rules (soft):** generation is encouraged to include and need all/most of the seen mechanics; the newest rule is always required.
- **Avoid-type rules (hazards, beacon_goal):** "forced" means the rule-blind shortest plan must fail on the real level, so the player has to notice the rule and detour; no near-optimal rule-blind route.
- **Targets before the 07:00 lock:** a new frozen `eval-v3` collection (fresh seeds; any model sweep on it is a separate human cost decision) and training data (A1/A3). Not the web "New game" switch for now.
- Opt-in only: `dev`, `train-v1`, `eval-v1`, `eval-v2` stay byte-identical.
- **Second RL run (Sat 20:05, ignacio):** grpo-2 on a second Modal H100 in parallel (~$16), game_turn only, 80 steps, from the SFT v2 `games` adapter; grpo-1 (70% game_turn + 30% aux, 150 steps) continues. Both runs' checkpoints are finalist candidates under the pre-registered rule.
- **eval-v3 (Sat ~21:30, Anssi; recorded by A7):** built by A7 with `gridforce` (30 games, d1/d2/d3 cycled, 6 levels, seeds 930000-930029, same shape as eval-v1). **Draft, not frozen. No model runs on eval-v3 (no sweeps, no Harbor export, no /challenge use) until Anssi has looked at it and says so.** A1 OK'd the A7 engine hooks verbally to Anssi.
- **Claude Sonnet 5.5 on eval-v2 (Sat 20:04, human, recorded by A4):** one game only, the Anthropic key has ~$7 left: `arena/sweeps/eval-v2-sonnet.yaml` (s910000, h1, medium, 400 actions, $6.50 hard cap; dry-run $6.40, under the $20 per-sweep cap). Single-attempt row. More Claude needs a key top-up.
- **eval-v3b (Sat ~20:30, Anssi request; recorded by A7):** second draft from the new `gridbranch` generator (more alternative routes, harder ramp), same seeds and shape as eval-v3. `gridforce` / eval-v3 kept unchanged so Anssi can choose. Same rule: no model runs on either until Anssi says so.
- **Post-training re-plan (Sat ~21:15, ignacio, recorded by A3):** the goal is a model that THINKS better. The no-thinking SFT v2 + grpo-1/grpo-2 line is stopped (it trained answer-only replies and dropped the base from 0.758 to ~0.44 on the dev-slice headline; kept as a documented negative result). New: GRPO with thinking ON from the base Qwen3.5-9B (fresh LoRA, no SFT), reward only on the answer after `</think>`: `think-games` (our game_turn + aux tasks) vs `think-ctrl` (generic reasoning-gym puzzles, same budget), two Modal H100s, ~$60, evaluated with thinking ON on the FT_BENCHMARKS dev slice.

- **RL restart on gridbranch (Sat ~22:00, Anssi; recorded by A7):** restart the `think-games` GRPO run on data from the `gridbranch` v2 generator (the eval-v3b one). Training source = new `train-v3b` (gridbranch, train seeds 300000-302999, hold-out filtered, 1,904 games), never eval-v3b itself. Handover to A2: `coordination/requests/A7-to-A2-restart-rl-on-gridbranch.md`.
