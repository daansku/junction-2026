# Research Digest — Interactive Reasoning Benchmarks, ARC-AGI-3 & AfterQuery Rubric

**Author:** A5 (LENS) · **Scope:** Actionable guidance for engine rules (A1), agent harness & fine-tuning (A3), and leaderboard/analysis design (A5).

---

## 1. What ARC-AGI-3 Changed (and Why Static Puzzles Are No Longer Enough)

Static input-output benchmarks (ARC-AGI-1, ARC-AGI-2) reward single-shot pattern extrapolation, yet modern reasoning models and test-time search loops can spend arbitrarily large hidden compute per puzzle without paying an explicit exploration cost. **ARC-AGI-3** shifts the problem to **interactive, pixels-only grid environments**:

- **Zero priors / zero instructions:** Agents receive a `64×64` frame over a 16-colour palette and discrete control actions (`RESET`, `ACTION1..7`), with no rule manual, score counter, or win/lose flags.
- **Four coupled bottlenecks:**
  1. **Exploration:** Discovering which sprite the player controls, what boundary/wall rules apply, and where resource bars live in the HUD.
  2. **Causal World Modeling:** Updating beliefs when actions produce zero motion (`bump`), non-local state transitions (`plates_gates`, `teleporters`), or continuous slides (`ice`).
  3. **Goal Inference:** Identifying the win condition without text hints, especially when colour semantics cannot be assumed across games (`skin_shuffle`).
  4. **Long-Horizon Planning & Budget Control:** Choosing shortest paths and deciding *when to issue `RESET`* before wasting actions on a broken attempt.
- **Relative Human Action Efficiency (RHAE):** Binary pass/fail hides the core gap. In ARC-AGI-3, solving a level in 48 actions when a first-time human needs 14 actions (or BFS needs 11) is penalized proportionally via action efficiency (`min(1, ref_moves / actions_used)`).

---

## 2. Lessons from ARC Prize 2024 & 2025 Winning Approaches

Across ARC Prize 2024 (*The ARChitects* et al.) and ARC Prize 2025 (*Evolutionary Program Synthesis*, *Tiny Recursive Models (TRM)*, *Refinement Loops*), three empirical findings translate directly into our stack:

1. **Test-Time Hypothesis Revision Beats Raw Pretraining Scale:**
   - Static zero-shot rollouts get stuck repeating zero-effect actions because the context lacks explicit causal feedback loops.
   - Winning systems maintain an explicit hypothesis state and verify predictions against state deltas (`diff_count` / pixel diffs).
   - **Action for A3 (`arena`):** Preserve structured `{notes, hypothesis, belief, action}` fields on every turn, and test an ablation adding deterministic cell-diff summaries vs. raw pixels/text so we measure whether failures come from *perception* or *reasoning*.

2. **Fine-Tuning Small Models on Process + Recovery Trajectories:**
   - ARC Prize 2024/2025 showed smaller specialized models (7M–12B) trained on synthetic transformations + refinement trajectories can beat much larger untuned frontier models on held-out tasks.
   - Crucial subtlety: training *only* on optimal paths produces brittle agents that loop endlessly the moment they make one off-optimal step or hit an unfamiliar skin.
   - **Action for A3 (`finetune`):** Build `train-v1` SFT trajectories with **both** optimal BFS demonstrations (~70%) and **mistake-recovery episodes** (~30%): hitting a wall/hazard, updating `notes` + `hypothesis`, recovering or calling `RESET` when deadlocked, and completing the level.

3. **Skin Shuffling Eliminates Memorization:**
   - In ARC-AGI, models routinely lean on surface priors ("green = goal", "red = bad", "yellow = key").
   - **Action for A1 (`engine`):** Permute colour + sprite skins per game (`skin_shuffle=True`) and hold out specific colour assignments and rule pairs for `eval-v1` vs `train-v1`.

---

## 3. Mapping Directly to the AfterQuery Challenge Rubric (`docs/CHALLENGE.md`)

Judges score 100 points across four criteria during a 10-minute demo plus a 15-minute live exploit hunt using **Harbor + OpenCode over MCP**:

| Criterion | Weight | How our design wins full points |
|---|---|---|
| **The Gap** | 30 pts | Frontier models evaluated on unseen seeded `eval-v1` games consistently score below both `optimal` (`1.000`) and first-attempt `human` baselines, with reproducible traces stored on the shared server. |
| **Meaningful Difficulty** | 30 pts | Every level is BFS-verified solvable, every active rule is proven *necessary* (neutralizing the rule changes optimal path length), and every state signal (moves left, health, held keys, level pips) is drawn in the `64×64` frame. No hidden timers or trick wording. |
| **Reward Integrity** | 25 pts | Headline score is mean per-level `min(1, optimal_moves / actions_used)` (`0` if unsolved). `noop` (0 actions) scores **0.000**. `stop_early` (5 actions, 0 levels solved) scores **0.000**. Reset farming strictly increases the denominator (`actions_used`) and lowers the score. Random walk passes < 2% of levels under budget. |
| **Craft + Tiebreaker** | 15 pts + tie | One-command evaluation (`python -m analysis build`, `make smoke`), open MCP interface (`python -m server mcp`), plus fine-tuned small model beating untuned frontier models on held-out `eval-v1` games. |

---

## 4. Concrete Recommendations Filed

- **For A1 (`rules/proposals/a5-*.md`):**
  1. `a5-delayed-state-switch.md` — temporal credit assignment via delayed/toggling state transitions.
  2. `a5-decoy-and-camouflage.md` — decoy goal / beacon correlation to defeat colour priors even more strongly.
  3. `a5-sokoban-deadlock-box.md` — irreversible corner deadlocks forcing models to detect unsolvable states and issue `RESET`.
- **For A3 (`coordination/requests/a5-to-a3-harness-and-finetune.md`):**
  - Keep `hypothesis` and `belief` structured, add `noop`/`stop_early` sweeps to every eval collection for continuous reward-integrity checks, and balance optimal + recovery SFT trajectories.
- **For A5 (`analysis/METRICS.md`):**
  - Track `actions_to_first_use`, `wasted_actions`, `repeated_no_effect_actions`, `hypothesis_match_rate`, and `belief_accuracy` per `(rule, player)` so we can automatically feed weak spots back into `rules/proposals/auto-*.md` (`eval-v2`).
