# Judge Q&A & 15-Minute Exploit Hunt Defense (`docs/QA_PREP.md`)

> Prepared for the AfterQuery 10-minute demo + 15-minute interactive exploit hunt + Harbor/OpenCode MCP rerun.
> **Rule:** Never overclaim. Cite only verified formulas, schema guards, test suites, and inspected trace metrics.

---

## Part A: Reward Exploit Hunt — Anticipated Attacks & Defenses

### Attack 1: *"Can an agent score points by solving only Level 1 quickly and aborting early before harder levels?"*
- **Why it fails:**
  1. `leaderboard.score` ALWAYS averages `level_score(L)` over all `levels_total` levels (`1..levels_total`), NOT just levels attempted (`analysis/METRICS.md §2`, `analysis/src/analysis/loader.py:332-354`).
  2. Solving only Level 1 of a 6-level game caps maximum possible score at `1 / 6 = 0.1667` (`Optimal` = `1.000`).
  3. Solving zero levels (`noop` or `stop_early`) yields strictly `0.000`, enforced automatically by `check_claims` (`analysis/src/analysis/claim_check.py:51-52`) and tested in `analysis/tests/test_analysis.py`.

### Attack 2: *"What if an agent explores noisily for 40 steps, sees how the puzzle works, hits `RESET`, and replays only the optimal path to fake a `1.000` efficiency ratio?"*
- **Why it fails:**
  - `actions_used(L)` counts **all** actions taken while in Level `L`, including steps prior to `RESET` and the `RESET` call itself (`analysis/src/analysis/loader.py:270-273, 338-346`).
  - Proven in `test_reward_integrity_and_reset_penalty`: a clean optimal solve in `4` moves scores `1.0`, whereas taking `2` exploration/reset steps followed by `4` optimal moves consumes `actions_used = 6`, capping score at `4/6 = 0.6667`.

### Attack 3: *"Can an agent farm partial credit by toggling switches, collecting keys, or bumping walls repeatedly?"*
- **Why it fails:**
  - Zero intermediate shaping reward is added to `level_score(L)`. Keys (`picked_key`), plates (`pressed_plate`), pushes (`pushed`), and teleports emit diagnostic events in `Truth` for post-hoc `rule_discovery.py` analysis ONLY — never score points.
  - Extra toggling/bumping increases `actions_used(L)` in the denominator and strictly hurts efficiency (`min(1.0, optimal_moves / actions_used)`). No-effect steps (`bump` or byte-identical playfield `rows 6..63`) are explicitly flagged in `no_effect_rate` and `no_effect_loop`.

### Attack 4: *"Can the agent inspect `Truth`, `optimal_path`, or hidden JSON state via MCP or REST responses?"*
- **Why it fails:**
  - Agent turns receive ONLY `frame` (or PNG) and `available_actions` (`contracts/openapi.yaml`, `server/src/server/app.py`, `arena/src/arena/agent_loop.py`).
  - The `/sessions/{id}/truth` endpoint is polling-only for the **harness/evaluator** to detect `WIN`/`GAME_OVER` transitions and log offline `steps.jsonl`; `arena/tests/test_arena.py` explicitly verifies `Truth` is never injected into agent prompts, and `server` MCP tools (`list_games`, `start_game`, `act`, `reset`) return only visual frames and allowed actions.

### Attack 5: *"Can an agent hardcode pixel colors (`yellow = key`, `green = goal`, `red = hazard`) across games?"*
- **Why it fails:**
  - Every generated game enables `skin_shuffle: true` (`data/fixtures/games.json`, `rules/CATALOG.md`), permuting the 16-color indexed palette per seed. An agent must identify mechanics by **geometry and dynamic affordances** (sprite shape + step transitions), not RGB memorization.

### Attack 6: *"What if the agent uses `ACTION1..4` out of bounds or spams invalid tool payloads?"*
- **Why it fails:**
  - Invalid/unrecognized actions either count against turn/step budgets or leave playfield `rows 6..63` unchanged (counted as wasted `no_effect` actions), while the top move-budget bar still decrements on valid moves. `GAME_OVER` locks every move except `RESET`.

### Attack 7: *"Could `analysis` tar sync be exploited with path traversal (`../`) from an untrusted export bundle?"*
- **Why it passes audit:**
  - `_safe_extract_tar_bytes` in `analysis/src/analysis/sync.py:29-50` resolves every member path against `runs_dir.resolve()`, rejects absolute paths, `".."`, single-segment files, and non-regular files, and is explicitly unit-tested in `test_sync_tar_extraction_and_traversal_guard`.

---

## Part B: Judge Methodology & Design Q&A

### Q1: *"Why choose a pixel-grid curriculum instead of a terminal / SWE / bash environment?"*
- Code/bash benchmarks heavily conflate **tool fluency on seen libraries** with genuine **zero-shot rule induction**. A 64×64 indexed pixel world with shuffled colors strips away pretrained natural-language hints while retaining fast, deterministic ground-truth verification (exact BFS `optimal_moves`, exact `random`-walk ceiling `< 2%`, sub-millisecond simulation). And critically, the *cognitive loop* — probe -> inspect state diff -> revise hypothesis -> manage scarce budget -> reset dead ends — transfers directly to unfamiliar debugging and tool-use environments.

### Q2: *"How do we know failures aren't caused by unfair ambiguity or impossible timing?"*
- Every level satisfies 4 engine invariants before it enters a collection (`rules/CATALOG.md`): BFS-solvable (`optimal_moves`), rule-necessary (ablation test proves every active rule changes the optimal path or solvability), bounded slack (`ceil(optimal_moves × slack)`), and visible affordances in the 64×64 grid (distinct shapes for arrows, X teleporters, checker plates, slotted doors, plus-sign hazards, HUD key/health pips, and top move-budget bar). If a frontier model fails, `/replay/<run_id>?step=<step>` lets you inspect exact pixels + model `hypothesis` + `belief` side by side.

### Q3: *"Why aren't frontier sweep results hardcoded in git if live API keys ran late?"*
- By design (`PLAN.md §3.4 & §4.6`), `data/derived/` is **never committed cleanly with stale claims** — only verified deterministic fixtures (`data/fixtures/derived/`) live in git as the CI baseline, while live sweeps on the shared server export via `python -m analysis sync && python -m analysis build` and must pass `python -m analysis check-claims`. That guarantees zero fabricated numbers anywhere in the repo or UI.

### Q4: *"How does the `eval-v2` proposal loop actually work?"*
- `python -m analysis insights --write-proposals` inspects `rules.json` (excluding passive Tier-0 rules with `intro_levels == 0`) to identify lowest `intro_solve_rate`, highest `wasted_actions`, and `repeated_no_effect_actions`, then writes grounded Markdown specifications into `rules/proposals/auto-*.md` (`auto-01-wall-bump-cooldown.md`, `auto-02-false-goal-indicator.md`, `auto-03-commitment-corridor.md`) citing exact observed metrics and replay failure counts for A1 to implement in the next benchmark revision.

### Q5: *"How do judges reproduce our setup using Harbor + OpenCode over MCP?"*
- Start the MCP stdio bridge against either a local server or the shared deployment URL:
  ```bash
  make server PORT=8000
  python -m server mcp --api http://localhost:8000
  ```
  It exposes `list_games`, `start_game`, `act`, and `reset` matching AfterQuery's MCP flow so Harbor + OpenCode can evaluate `optimal` (or human reference), `3 × frontier agent`, `noop`, and `stop_early` identically.
