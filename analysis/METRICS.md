# Metrics Specification (`analysis/METRICS.md`)

Exact mathematical definitions for every derived table in `data/derived/` and `data/fixtures/derived/`, matching `contracts/trace.schema.json`, `contracts/derived.schema.json`, and `PLAN.md §4.6`.

---

## 1. Run Hygiene & Trace Attribution (`steps.jsonl` → Per-Level Segments)

### Benchmark Run Hygiene (`filter_benchmark_runs`)
Before aggregation, `load_runs(..., clean=True)` removes non-benchmark noise from shared server exports (`PLAN.md §3.2`, `coordination/OVERNIGHT.md`):
1. **Unlabelled practice humans & mid-run take-overs:** `player.kind == "human"` with `name/id` in `{"anonymous", "test"}` (intentional labelled human baseline runs use `--player human:<label>`), plus any session with `meta.start_level` or `meta.takeover_of` set (`COORDINATION.md` §3: `[ TAKE OVER FROM STEP N ]` sessions jump straight into level $L$ and are never counted in baselines).
2. **Smoke checks:** `player.id` starting with `"smoke-"`.
3. **Infrastructure / timeout aborts:** runs with `end_reason == "idle_timeout"`, or `player.kind == "model"` with `outcome == "ABORTED"` (provider disconnects, 530 tunnel drops, or interrupted batch pools), while preserving intentional reward-integrity baselines (`noop`, `stop_early`, `random`) whose `outcome` may be `"ABORTED"`.
4. **Superseded collection game IDs:** runs tagged with a collection (`dev`, `eval-v1`, `smoke`, `showcase`) whose `game_id` is no longer in the active `data/collections/<collection>.json` (e.g., `engine 0.2.0` game hashes replaced when `dev.json` upgraded to `engine 0.5.0`).

### Per-Level Trace Attribution
Each finished run consists of `meta.json` and `steps.jsonl`:

- **Initial frame (`i = 0`, `action = null`):** records the initial `truth` of Level 1 (`level = 1`, `optimal_moves`, `active_rules`, `new_rule`).
- **Action step (`i >= 1`, `action != null`):** executes `action` from **pre-state** `prev_truth = steps[i - 1].truth` and produces **post-state** `curr_truth = steps[i].truth`.
- **Level attribution:** Step `i` belongs to level `L = prev_truth.level`, with:
  - `optimal_moves(L) = prev_truth.optimal_moves`
  - `active_rules(L) = prev_truth.active_rules`
  - `new_rule(L) = prev_truth.new_rule`
  - If a trace begins at `i = 0` with `action != null` (synthetic/legacy edge case), pre-state falls back to `steps[i].truth`.
- **Level completion condition:** Level `L` is marked **solved** if any step `i` attributed to `L` satisfies:
  - `"level_complete" in curr_truth.events`, OR
  - `curr_truth.level > L`, OR
  - `curr_truth.state == "WIN"` (final level).
- **Actions used on level `L`:** `actions_used(L)` is the total count of steps `i >= 1` attributed to level `L`, **including** any actions taken before a `RESET` and the `RESET` action itself.

---

## 2. Headline Efficiency Score (`leaderboard.json`)

Adopted from ARC-AGI-3's action-efficiency scoring (`PLAN.md §4.6` & `contracts/derived.schema.json`):

For each level $L \in \{1, \dots, \text{levels\_total}\}$ of a game:

$$
\text{level\_score}(L) = \begin{cases}
\min\!\left(1.0,\; \dfrac{\text{optimal\_moves}(L)}{\text{actions\_used}(L)}\right) & \text{if level } L \text{ is solved and } \text{actions\_used}(L) > 0 \\
1.0 & \text{if level } L \text{ is solved and } \text{optimal\_moves}(L) = 0 \\
0.0 & \text{if level } L \text{ is not solved}
\end{cases}
$$

- **Game score:** $\dfrac{1}{\text{levels\_total}} \sum_{L=1}^{\text{levels\_total}} \text{level\_score}(L)$.
- **Leaderboard `score`:** Mean of `level_score(L)` across all levels $L$ of all runs grouped by `(player_id, kind, effort, collection, harness_version)`.

### Leaderboard Row Fields
- **`player_id`:** `player.model_id` for models, or `"random" | "optimal" | "human" | "noop" | "stop_early"` (normalising `"baseline:random"` → `"random"`).
- **`games`:** Number of runs in the group.
- **`levels_attempted`:** $\sum \text{levels\_total}$ across runs in the group (ensures early stopping cannot inflate solve rates).
- **`level_solve_rate`:** $\dfrac{\sum \text{levels\_solved}}{\text{levels\_attempted}} \in [0, 1]$.
- **`game_win_rate`:** Fraction of runs with `outcome == "WIN"` (or `levels_completed == levels_total`).
- **`median_actions`:** Median `meta.actions` across runs in the group (`null` if no runs).
- **`tokens_in`, `tokens_out`:** Total input and output tokens across runs in the group (`null` for non-LLM baselines/humans).
- **`cost_per_game`:** $\dfrac{\sum \text{cost\_usd}}{\text{games}}$ (`null` if pricing is unknown).
- **`cost_per_solved_level`:** $\dfrac{\sum \text{cost\_usd}}{\sum \text{levels\_solved}}$ (`null` if 0 levels solved or pricing unknown).
- **`latency_ms_median`:** Median `step.latency_ms` across action steps with non-null latency.
- **`input_modes`:** Observation modalities supplied by `h1` (`["image", "rle"]` for multimodal VLMs; `["rle"]` for text-only models, ensuring identical lossless 64×64 grid information).
- **`seen_score`, `unseen_pair_score`, `unseen_skin_score`:** Hold-out split sub-scores on `eval-v1` (`game_desc.holdout.levels` lists 1-based levels containing held-out rule pairs and `game_desc.holdout.skin` flags held-out palette/glyph skins; `null` on collections without hold-out annotations).
- **`rhae_vs_human`:** Ratio `score / human_score` when a `human` row exists in the same collection (`null` otherwise).

---

## 3. Reward Integrity Properties (AfterQuery Rubric §3)

1. **`noop` baseline (0 actions):** `levels_solved = 0` ⇒ `score = 0.000`.
2. **`stop_early` baseline ($k$ actions before solving Level 1):** `levels_solved = 0` ⇒ `score = 0.000`.
3. **Reset farming:** Calling `RESET` increments `actions_used(L)` without decreasing `optimal_moves(L)`, strictly decreasing `level_score(L)`.
4. **Random walk:** Levels are rejected by the generator if random walk wins $\ge 2\%$ of tries; random-walk `score` stays near `0.0`.
5. **Unseen skill transfer:** `optimal` scores `1.000`, `human` scores substantially above untuned frontier models on multi-rule levels.

---

## 4. Rule-Discovery Metrics (`rules.json`)

For each `(rule, player_id, effort)` across all level segments where `prev_truth.new_rule == rule` (introducing levels; if a collection sets `new_rule == null` on Level 1, Level 1's base rules `"walls"`, `"goal"`, `"move_budget"` are attributed when explicitly listed in `active_rules`):

- **`intro_levels`:** Count of introducing level attempts for `rule`.
- **`intro_solve_rate`:** Fraction of introducing levels solved.
- **`actions_to_first_use`:** Median step index (1-based within the introducing level attempt) at which the player first triggers an interaction event associated with `rule`:
  - Tier 1 (`engine 0.2.0`): `keys_doors` (`picked_key`, `opened_door`), `plates_gates` (`pressed_plate`), `teleporters` (`teleport`), `hazards` (`hurt`, `level_complete`), `push_blocks` (`pushed`), `ice` (`slid:*`), `one_way` (`bump`, `level_complete`)
  - Tier 2 (`engine 0.5.0`): `collect_all` (`collected`, `goal_locked`), `phase_walls` (`phased`, `wait`), `rotation` (`rotated:*`), `remap` (`level_complete`), `twin` (`bump`, `level_complete`), `stamina` (`wait`, `exhausted`), `cracked_floor` (`floor_collapsed`), `beacon_goal` (`decoy`)
  - Tier 3 (`engine 0.5.0` opt-in `eval-v2`): `conveyors` (`conveyor:*`), `enemies` (`enemy_hit`), `gravity` (`fell:*`)
  - Tier 0 (`walls`, `goal`, `move_budget`): `bump`, `reset`, or `level_complete`
  - If the level is solved without emitting an explicit named event (e.g. `one_way` traversed purely along arrows), falls back to the optimal/completion step count on solved levels (`null` if never triggered or solved).
- **`wasted_actions`:** Mean excess actions on introducing levels: $\max(0, \text{actions\_used}(L) - \text{optimal\_moves}(L))$ if solved, else $\text{actions\_used}(L)$.
- **`repeated_no_effect_actions`:** Mean count of steps on introducing levels where `"bump" in curr_truth.events` OR (when `action != "RESET"` and the playfield rows `6..63` are byte-identical between `prev_frame` and `curr_frame`).
- **`hypothesis_match_rate`:** Fraction of introducing level runs where at least one step's `hypothesis` or `reasoning` matches canonical semantic keywords for `rule` (or `null` for non-reasoning baselines/humans).
- **`belief_accuracy`:** Fraction of steps where `belief` matches `truth.state` (`NOT_FINISHED -> "playing"`, `WIN -> "won"`, `GAME_OVER -> "lost"`).
- **`recombined_solve_rate`:** Solve rate on *later* levels (`new_rule != rule`) where `rule in active_rules`.

---

## 5. Cross-Level Learning & Failure Taxonomy (`insights.json`)

- **Level curve (`level_curve`):** Mean solve rate and efficiency `score` by level number `1..6` across player tiers (`optimal`, `human`, `finetuned`, `frontier`, `open`, `baseline`).
- **Failure taxonomy (`failure_modes`):** Counts and rates of:
  1. `no_effect_loop` (`repeated_no_effect_actions >= 2` or consecutive bumps)
  2. `budget_exhaustion` (`outcome == "BUDGET"` or `"out_of_moves"` / `"level_lost"`)
  3. `late_reset` (issued `RESET` after spending $> 1.5\times \text{optimal\_moves}$ or never reset after soft-lock)
  4. `belief_mismatch` (`belief != expected_belief_from_state`)
  5. `rule_blindness` (failed introducing level with `hypothesis_match == False`)
- **Automated rule proposals (`rules/proposals/auto-*.md`):** Generated whenever a rule exhibits `intro_solve_rate < 0.50` or high wasted/no-effect rate, directly linking the failure evidence to a concrete Tier 2/3 mechanic for `eval-v2`.

---

## 6. Per-Level Failure Explanations (`explanations.json`)

Built by `python -m analysis explain` (and incrementally preserved during `python -m analysis build`), validated against `contracts/derived.schema.json#/$defs/explanations`.

### Scope & Packet Construction
For every attempted failed level (`actions_used > 0` and `solved == False`) on a `model` run:
- Ground-truth level metadata: `active_rules`, `new_rule`, `optimal_moves`, `move_budget`, and BFS `optimal_path` (arrow sequence from `game.describe()`).
- Step-aligned trace excerpt: 1-based step index `i`, `action`, `truth.events`, `no_effect` flag, and verbatim `hypothesis` / `reasoning` strings from `steps.jsonl`.

### Judge Prompt & Output Contract
- **Cost check first:** `python -m analysis explain --estimate` outputs `failed_levels`, `est_tokens_in`, `est_tokens_out`, `est_cost_fast_judge_usd`, `est_cost_sonnet_judge_usd`, and `within_decisions_sweep_cap` (`<= $20.00`).
- **System prompt (`JUDGE_SYSTEM_PROMPT`):** Instructs the judge model (which sees ground truth that playing models never see) to return strict JSON:
  - `run_id` (`string`), `game_id` (`string | null`), `player_id` (`string | null`), `level` (`integer >= 1`)
  - `step` (`integer | null`): exact 1-based step `i` in `steps.jsonl` where the failure crystallizes
  - `rule` (`string | null`): canonical rule slug misunderstood by the model
  - `verdict` (`string`): `never_used_rule | wrong_hypothesis | ignored_no_effect | late_reset | hazard_loss | ran_out_of_budget`
  - `explanation` (`string`): concise diagnosis of what failed at `step` and what the optimal path required
  - `evidence_quote` (`string | null`): **verbatim** contiguous substring copied from the model's `hypothesis` or `reasoning` on that level (verified by `_verify_quote_in_steps`; non-verbatim LLM quotes are rejected in favour of verified substrings)
  - `judge_model` (`string`): model identifier (or `"trace-auditor-v1"` when synthesized deterministically offline)


---

## 7. Lab-Standard Evaluation & Confidence Intervals (`leaderboard_h2.json`, Phase 2 `A5-20`)

### Strict Harness Separation (`PLAN.md` §1.1 & §3.1)
- `leaderboard.json` aggregates **only** `h1` model runs (`harness_filter == "h1"`, stateless rolling-notes harness) plus reference baselines/humans.
- `leaderboard_h2.json` aggregates **only** `h2` model runs (`harness_filter == "h2"`, multi-turn conversation + preserved reasoning blocks + native `act(action, hypothesis, belief)` tool + `high`/`max` effort + `64k`/`32k` output cap + last-5 image frames with prompt caching) plus reference `Optimal` and `Human` rows matched to the `h2` game subset per collection.
- **Additional Phase 2 Run Hygiene (`loader.py`):**
  - Visitor kiosk runs from `/challenge` (`player.mode == "challenge"` or `player.purpose == "challenge"`) and assisted `/play` runs (`assisted == True`) are excluded from benchmark tables.
  - Pre-`2026-11-14T15:35:00Z` `h2` runs ending with `end_reason == "budget_tokens"` (3M cached-context token counter bug) are dropped.
  - Pre-`2026-11-14T15:15:00Z` Gemini `h1` rows are flagged with `cost_underreported = true` and `cost_note` (`~3.6x` undercount before `billed_tokens` included thinking tokens).

### Bootstrap 95% Confidence Intervals
For any row with $G \ge 2$ game runs and per-game scores $s_1, \dots, s_G$:
- Draw $B = 10{,}000$ bootstrap resamples of size $G$ with replacement (deterministic seed `20261114`).
- `score_ci_low` and `score_ci_high` are the 2.5th and 97.5th percentiles of the resampled mean game score.
- Single-attempt evaluations (`attempts_per_game == 1.0`) set `single_attempt = true` and append `"single-attempt (k=1)"` to `subset_note`.

---

## 8. Post-Training & Outside-Benchmark Transfer (`bench_summary.json`, Phase 2 `A5-20`)

Built by `analysis/src/analysis/bench_agg.py` from `data/derived/bench/<run>/{summary.json,items.jsonl}` (`bench/PROTOCOL.md` v2 & `FT_BENCHMARKS.md`):

- **Primary Far-Transfer Suite (6 benchmarks, unweighted mean = headline):**
  1. `bbh` (`bbh_cot_fewshot`, all 27 tasks, 3-shot CoT, ~6,511 items)
  2. `math` (`minerva_math`, 0-shot CoT, 5,000 items)
  3. `gsm8k` (`gsm8k_cot`, 8-shot CoT, 1,319 items)
  4. `medqa` (`medqa_4options`, 0-shot 4-option loglikelihood, 1,273 items)
  5. `mmlu_pro_health` (5-shot CoT)
  6. `mmlu_pro_law` (5-shot CoT)
- **Negative Control (`negative_control`):** `mmlu_pro_history` (5-shot CoT, knowledge recall — must not rise like the primary suite).
- **Pre-Declared BBH Logic Subset (`bbh_logic_secondary`):** `tracking_shuffled_objects`, `navigate`, `logical_deduction`, `web_of_lies`, `temporal_sequences` (sliced directly from `bbh` items).
- **Paired Item-Level Bootstrap (`paired_delta_ci`):** For candidate $C$ vs reference $R \in \{\text{base}, \text{ctrl}\}$ over shared items $I = I_C \cap I_R$ ($n = |I|$), bootstrap $d_k = c_k - r_k$ $10{,}000$ times (seed `20261114`); `excludes_zero = (ci_low > 0) or (ci_high < 0)`. Unshared items are dropped and counted (`n_only_ref`, `n_only_cand`), never imputed.
- **Pre-Registered Honesty Claim Rule (`_evaluate_honesty_rule`):** Sets `transfer_shown = true` (`status = "transfer_supported"`) **if and only if** a trained candidate (`games`, `mix`, or `rl-*` finalist) beats equal-token `ctrl` on the primary suite mean **and** on $\ge 2$ primary benchmarks with 95% CIs excluding zero, **and** its `mmlu_pro_history` delta vs `ctrl` is strictly smaller than its primary headline delta (with no $>2$ pp significant guard drop vs `base`). Otherwise reports `null_transfer_in_domain_only` or `pending_bench_runs` plainly.

---

## 9. Failure-Targeted Decision Points & Oversampling (`decision_points.json`, Phase 2 `A5-21`)

Built by `analysis/src/analysis/sampling_export.py` (with holdout-safe `dev`-only target weights committed at `analysis/decision_point_targets.json` for `A1` and `A3`):
- Extracts crisp failure decision points across `premature_hypothesis`, `zero_change_wall_bump`, `late_reset`, and `missed_new_rule`.
- Computes normalized oversampling mixture weights over `dev`-only failures, explicitly excluding `eval-v1`, `eval-v2`, `probe-v1`, and Tier-3 holdout mechanics (`conveyors`, `enemies`, `gravity`) so training data synthesis never leaks held-out evaluation distributions.

---

## 10. Truth-Diffed Reasoning Forensics & Cognitive Bottleneck Funnel (`explanations.json`, `A5-24`)

Built by `analysis/src/analysis/explain.py` (`reasoning-auditor-v2` + optional `arena judge` LLM pass via `--export-prompts` / `--import-replies` / `--judge-arena`):

- **Why Pure CoT Text Classification Is Insufficient:** Models frequently write plausible-sounding post-hoc rationalizations in `<think>` or rolling scratchpad notes when bumping into walls or misreading coordinates. Therefore, LENS never classifies `step.reasoning` in isolation — every reasoning block is **diffed against hidden engine `truth`** (`events`, `[NO_EFFECT]` playfield-unchanged check, `active_rules`, `new_rule`, and BFS `optimal_path`).
- **Reasoning Provenance (`reasoning_source`):**
  - `cot`: `h2` Chain-of-Thought `<think>` / reasoning blocks.
  - `notes`: `h1` rolling structured scratchpad notes.
  - `hypothesis_only`: `step.reasoning` is unpopulated because the provider encrypts thinking tokens (e.g. `gemini-pro` `thought_signature` on `h2`), while `step.hypothesis` is populated.
  - `none`: neither `reasoning` nor `hypothesis` recorded.
- **Deterministic Inflection-Window Slicer (`slice_inflection_windows`):** Extracts $\pm 2$-step windows around initial orientation, first `new_rule` event, first mechanic deduction in CoT/notes, `no_effect` streak onset, `belief != expected_belief` mismatches, adverse events (`hurt`, `decoy`, `floor_collapsed`, `checkpoints_reset`, `enemy_hit`), and `RESET`/terminal steps — pairing **both** `reasoning` and `hypothesis` with engine `truth`.
- **5-Stage Cognitive Bottleneck Funnel (`cognitive_stage` & `root_cause`):**
  1. `perception` (`coordinate_misread`): Fails pure Tier-0 wall/goal geometry or hallucinates motion/win state across zero-effect moves.
  2. `rule_induction` (`unprobed_new_rule` | `false_rule_hypothesis`): Never articulates the active non-Tier-0 mechanic prior to failure.
  3. `belief_updating` (`ignored_falsifying_feedback`): Repeats blocked/zero-pixel-change actions ($\ge 3$ consecutive `[NO_EFFECT]` steps) without revising its plan.
  4. `spatial_planning` (`knew_rule_failed_rollout` | `hazard_collision`): **The Knowing–Doing Gap** — explicitly articulates the active hidden mechanic in CoT/notes (`deduced_rule_in_cot = true` at `deduced_rule_step < terminal_step`) yet fails multi-step spatial rollout or collides with hazards during execution.
  5. `budget_management` (`sunk_cost_late_reset`): Delays `RESET` until remaining move budget cannot cover `optimal_moves`.
- **Programmatic Verbatim Quote Verification:** Every `evidence_quote` (`quote_source` $\in \{\text{reasoning}, \text{hypothesis}\}$) is strictly verified as an exact contiguous substring of the recorded step text (`quote in step[quote_source]`).
