# Metrics Specification (`analysis/METRICS.md`)

Exact mathematical definitions for every derived table in `data/derived/` and `data/fixtures/derived/`, matching `contracts/trace.schema.json`, `contracts/derived.schema.json`, and `PLAN.md §4.6`.

---

## 1. Trace Attribution (`steps.jsonl` → Per-Level Segments)

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
  - `keys_doors`: `picked_key`, `opened_door`
  - `plates_gates`: `pressed_plate`
  - `teleporters`: `teleport`
  - `hazards`: `hurt` (or avoiding hazard to `level_complete`)
  - `push_blocks`: `pushed`
  - `ice`: `slid:*`
  - `one_way`: `bump` (or directional pass reflected by `level_complete`)
  - `walls` / `goal` / `move_budget`: `bump`, `reset`, or `level_complete`
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
