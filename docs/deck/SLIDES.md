# Presentation Deck Outline (`docs/deck/SLIDES.md`)

> Standalone interactive deck: open `docs/deck/index.html` in any browser (`←` / `→` / `Space` / `Home` / `End`).
> Every number in this deck is verified against `data/fixtures/derived/{leaderboard,rules,insights}.json` via `python -m analysis check-claims --derived data/fixtures/derived`.

---

## Slide 1 — Title: Pixels-Only Inductive RL Curriculum
- **Headline:** Can Frontier Agents Discover Unknown World Rules Without Text Hints?
- **Subtitle:** procedurally seeded 64×64 pixel environments · BFS-verified solvability · action-efficiency scoring
- **Visual:** 16-color indexed palette bar (`contracts/palette.json`) + curriculum pipeline (`walls + goal` → `1 new rule/level` → `multi-rule exam`).

## Slide 2 — Why Existing Agent Benchmarks Leak
- **Text priors bypass discovery:** English prompts like *"step on the blue switch to open the door"* turn world-modeling into instruction-following.
- **Static levels get memorized:** Fixed layouts and colors leak across training cutoffs.
- **Our constraint:** Zero prose instructions. Only a 64×64×16 frame (`rows 0–1`: move budget bar, `rows 3–4`: level pips & HUD, `rows 6–63`: playfield) plus `skin_shuffle: true` permuting object colors per game seed.

## Slide 3 — Engine & Curriculum Design (`Meaningful Difficulty`: 30 pts)
- **Tier 0:** `walls`, `goal`, `move_budget`.
- **7 Live Tier-1 Mechanics (`engine 0.2.0`):** `keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `one_way`, `ice`.
- **4 Mathematical Fairness Proofs per Level:**
  1. Exact BFS shortest path (`optimal_moves`, `optimal_path`).
  2. Rule-necessity check (removing any active rule changes optimal path length or breaks solvability).
  3. Bounded budget slack (`ceil(optimal_moves × slack)`).
  4. Random-walk win probability `< 2%` (`random` fixture achieves `0.008`).

## Slide 4 — Reward Integrity by Construction (`Reward Integrity`: 25 pts)
- **Headline formula (`analysis/METRICS.md`):**
  $$\text{level\_score}(L) = \begin{cases} \min(1.0,\; \text{optimal\_moves}(L) / \text{actions\_used}(L)) & \text{if solved} \\ 0.0 & \text{otherwise} \end{cases}$$
- **Four anti-exploit invariants (tested in `analysis/tests/test_analysis.py`):**
  1. `noop` (`0` actions) scores strictly **`0.000`**.
  2. `stop_early` (`5` actions before solving L1) scores strictly **`0.000`** — denominator is always `levels_total`.
  3. Reset farming strictly hurts score: `actions_used(L)` includes all actions taken before `RESET` plus `RESET` itself.
  4. `Truth` (`optimal_moves`, `events`, `active_rules`, `new_rule`) never leaves the server/harness.

## Slide 5 — Benchmark Gap & Verified Baseline Results (`The Gap`: 30 pts)
- **Data source (`data/fixtures/derived/leaderboard.json`, 13 evaluated runs):**
  - `Optimal` (`optimal` baseline): **`1.000`** (`15/15` levels solved, `0` resets, `0.0%` no-effect rate)
  - `Mock Model` (`fixture-run-0001`, subset `1/3` dev games): **`0.252`** (`2/6` levels solved: L1 `5/7 = 0.714`, L2 `16/20 = 0.800`, L3–6 `0.000`, `1` reset, `3.33%` no-effect, `$0.1439/game`)
  - `Random` (`random` baseline): **`0.008`** (`1/15` levels solved, `32.17%` no-effect, `31` resets)
  - `Noop` & `Stop Early`: **`0.000`** (`0/15` levels solved)
- **Live Sync Ready:** `python -m analysis sync && python -m analysis build` replaces fixture runs with live frontier & human sessions identically.

## Slide 6 — Rule-Discovery Forensics & Replay Deep Links
- **Why agents burn budget:**
  - `no_effect_loop`: repeating moves with byte-identical playfield (`rows 6..63`) or `"bump"` (`fixture-run-0001 @step 10`).
  - `late_reset`: triggering `RESET` after walking deep into wasted trajectories (`fixture-run-0001 @step 11`).
  - `budget_exhaustion`: failing downstream levels before completion (`4` runs hitting limit, `fixture-run-0001 @step 30`).
- Every insight chip on `/insights` deep-links directly into `/replay/<run_id>?step=<step>` showing the exact pixels, `hypothesis`, `reasoning`, and `belief`.

## Slide 7 — Self-Improving `eval-v2` Loop & Tier-2 Proposals
- **Automated proposal synthesis (`python -m analysis insights --write-proposals`):** reads lowest-performing `intro_levels > 0` mechanics and failure modes to emit grounded specs:
  - `auto-01-wall-bump-cooldown.md` (penalizes repeated zero-diff wall bumps)
  - `auto-02-false-goal-indicator.md` (requires sub-goal collection before goal activation)
  - `auto-03-commitment-corridor.md` (tests early dead-end recognition + timely `RESET`)
- **Hand-designed Tier-2 specs:** `a5-delayed-state-switch.md`, `a5-decoy-and-camouflage.md`, `a5-sokoban-deadlock-box.md`.

## Slide 8 — Reproducibility, MCP & One-Command Eval (`Craft`: 15 pts)
- **Harbor + OpenCode over MCP:** `python -m server mcp --api http://localhost:8000` (`list_games`, `start_game`, `act`, `reset`).
- **One-Command Judge Suite:** `make setup && make test && python -m analysis build --fixtures && python -m analysis check-claims --derived data/fixtures/derived`
- **Automated Verification:** `5/5` analysis tests pass + JSON Schema Draft 2020-12 `check-claims` (`0` errors) + strict TypeScript Vite UI build (`dist/`).
