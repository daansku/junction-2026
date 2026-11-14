# Pitch Narrative — AfterQuery @ Junction 2026

> **Duration target:** 10 minutes live (demo + architecture + rubric proof) followed by 15-minute live judge exploit hunt.
> **Core thesis:** Frontier agents do not fail grid benchmarks because they lack vision or arithmetic — they fail **inductive world-modeling under strict move budgets**: acting on stale assumptions across hidden mechanics, ignoring zero-diff actions, and exhausting reset budgets without updating their hypothesis.

---

## 1. The Problem We Chose to Measure (0:00 – 1:30)

Look at what AfterQuery asked: *build an RL environment where a strong reference run beats today's best agents, mistakes are meaningful and debuggable, and rewards cannot be hacked.*

Static puzzle benchmarks fail for two reasons:
1. **Text leaks rules:** If an environment tells an agent *"blue squares are ice and yellow squares are keys"*, the agent plays pattern-matching over pretrained English priors instead of learning from interaction.
2. **Contamination & visual shortcuts:** Static level packs get memorized, and fixed colors get hardcoded.

Our environment drops players — humans, frontier LLMs, fine-tuned open models, and algorithmic baselines — into **procedurally seeded 64×64 pixel curriculum games (`engine 0.2.0`)**:
- **Zero prose rules:** Only a 16-color indexed pixel frame (`rows 0–1`: move budget bar, `rows 3–4`: level pips & inventory/health HUD, `rows 6–63`: playfield).
- **Skin shuffle per game:** Every game seed permutes object colors (`skin_shuffle: true`). Knowing `"yellow = door"` on Game A misleads you on Game B.
- **Graduated inductive curriculum:** Level 1 introduces walls and the goal. Each subsequent level introduces **one new rule** from our 7 live Tier-1 mechanics (`keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `one_way`, `ice`) on a compact teaching grid, before a final multi-rule exam level recombines previously seen rules without any hint.

---

## 2. Why Every Failure Is Fair & Meaningful (`Meaningful Difficulty` — 30 pts) (1:30 – 3:30)

Before any generated game is served, the engine runs four deterministic proofs:
1. **BFS Solvability & Optimality:** Every level has a verified shortest-path solution (`optimal_moves`, `optimal_path`).
2. **Rule-Necessity Check:** Every active rule in a level genuinely alters the optimal path or solvability — there are no cosmetic props or fake difficulty walls.
3. **Budget Slack:** `move_budget = ceil(optimal_moves × slack)` gives humans and thoughtful agents room to experiment on an unfamiliar mechanic cleanly, while punishing aimless wandering.
4. **Random-Walk Rejection:** Any candidate level where a random policy wins ≥ 2% of trials is rejected at generation time.

Because `optimal_path` exists for every level and the HUD clearly displays the remaining move budget, level pips, and active state changes (`picked_key`, `pressed_plate`, `hurt`), an agent **has every piece of information needed to succeed** — just like a human opening an arcade puzzle with no manual.

---

## 3. Reward Integrity by Construction (`Reward Integrity` — 25 pts) (3:30 – 5:30)

Adapted from ARC-AGI-3's RHAE scoring, our headline metric scores **how close a player gets to optimal play per level, averaged over the entire game**:

$$\text{level\_score}(L) = \begin{cases} \min\!\left(1.0,\; \dfrac{\text{optimal\_moves}(L)}{\text{actions\_used}(L)}\right) & \text{if level } L \text{ is solved} \\ 0.0 & \text{if level } L \text{ is not solved} \end{cases}$$

Four properties make this metric resistant to shortcut exploitation (verified in `analysis/tests/test_analysis.py` and `python -m analysis check-claims`):
- **`noop` baseline scores strictly `0.000`:** Doing nothing solves zero levels.
- **`stop_early` baseline scores strictly `0.000`:** Taking `k` arbitrary actions without finishing Level 1 earns zero partial credit; scores always divide by `levels_total`, never by levels attempted.
- **Reset farming hurts your score:** `actions_used(L)` counts **all** actions spent on Level `L`, including every step prior to a `RESET` and the `RESET` call itself. Resetting early to undo a soft-lock limits damage; resetting late or repeatedly strictly lowers `optimal_moves / actions_used`.
- **`Truth` never leaves the server/evaluator:** Agent prompts and MCP tool responses return only the 64×64 pixel grid (`frame`), PNG image, and `available_actions` — never `optimal_moves`, `active_rules`, `new_rule`, or hidden events.

---

## 4. What the Pipeline Already Proves & Live Diagnostics (`The Gap` — 30 pts) (5:30 – 8:30)

In our verified fixture trace (`fixture-run-0001`, 6-level curriculum game `gridworld-s2-d2-l6-f978fc99`) compared against deterministic baselines across the `dev` fixture collection (`data/fixtures/derived/leaderboard.json`):
- **Optimal baseline (`optimal`):** `1.000` (`15/15` levels solved, `0` resets, `0.0%` no-effect actions).
- **Evaluated trace (`mock-model`, `fixture-run-0001`):** `0.252` (`0.252381`, `2/6` levels solved — `5/7` on Level 1, `16/20` on Level 2, `0.000` on Levels 3–6), with `1` wall bump (`@step 10`, `3.33%` no-effect rate) and `1` late reset (`@step 11`) before exhausting its `30`-step budget (`@step 30`).
- **Random walk (`random`):** `0.008` (`0.007752`, `1/15` levels solved, `32.17%` no-effect rate, `31` resets).
- **`noop` & `stop_early`:** `0.000` (`0/15` levels solved).

*(For live judging, we swap `--fixtures` for the live sweep traces + human baseline sessions via `python -m analysis sync && python -m analysis build` — every claim on `/leaderboard` and `/insights` automatically updates and passes `python -m analysis check-claims` before we step on stage.)*

Even more importantly for research, our **LENS analysis pipeline** decomposes traces down to the exact step (`analysis/src/analysis/rule_discovery.py`):
- **Rule × Player Discovery Matrix:** tracks `intro_solve_rate`, `recombined_solve_rate`, `actions_to_first_use`, `wasted_actions`, `hypothesis_match_rate`, and `repeated_no_effect_actions`.
- **Self-Improving `eval-v2` Loop:** bottom rule discovery metrics automatically synthesize `rules/proposals/auto-*.md` (`auto-01-wall-bump-cooldown.md`, `auto-02-false-goal-indicator.md`, `auto-03-commitment-corridor.md`) citing exact failure signals so level designers can systematically target newly observed agent blind spots.

---

## 5. Why This Matters Beyond Games (`Craft` — 15 pts) (8:30 – 10:00)

A software or scientific agent dropped into an unfamiliar codebase, API, or lab instrument faces the exact same loop as our grid world:
- Form an explicit hypothesis (`hypothesis`) from partial visual/state feedback.
- Probe safely without burning irreversible budget.
- Recognize when an action had zero effect or caused a dead-end (`RESET` early).
- Transfer a discovered rule when combined with other constraints later (`exam` levels).

Everything is reproducible from one command (`make setup && make test && python -m analysis build --fixtures && python -m analysis check-claims`), connectable over **MCP** (`python -m server mcp`) for **Harbor + OpenCode**, and backed by step-accurate replay links across every insight card.
