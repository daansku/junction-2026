# A7 — WARDEN: instructions

You are **agent A7 (WARDEN)**. Your job: **make level generation force the player to interact with each level's
new mechanic**, so that a player who avoids or ignores it cannot get anywhere near the optimal score.
A human (Anssi) starts you. **Ask clarifying questions whenever a choice is his (or A1's) to make; do not guess.**
The questions at the end are the minimum.

Read `PLAN.md` §1–§4 first (scope, gates, ownership), `coordination/PLAN-v1.md` §3 (working rules) and §5 (game design
rules), then this file.

---

## 1. The problem

Every level after level 1 introduces one new hidden rule (keys/doors, ice, teleporters, hazards, one-way tiles, plates
and gates, conveyors, ...). The generator already checks, on every level (`engine/src/engine/generator/__init__.py`):

- solvable (BFS over the full state),
- **every active rule "matters"** (`rule_matters()`): the optimal plan of a player who ignores the rule is longer,
  impossible, or fails on the real level,
- move budget = `ceil(optimal × slack)` (`SLACK = {1: 3.0, 2: 2.5, 3: 2.0, 4: 1.5}`, + `INTRO_ALLOWANCE` on teaching levels),
- a random walk wins < 2% of 200 tries.

**The gap:** "matters" passes when ignoring the rule changes the optimal length by **any** amount, even one move.
So many levels let a player route around the mechanic (walk around the hazard, never step on the ice, never use the
teleporter) and still finish at or near optimal efficiency. Our failure analysis shows it: models spend most failed
steps bumping walls (`no_effect_loop`, 71 of 89 failure verdicts are `ignored_no_effect`), and some solve levels
without ever touching the new rule (`never_used_rule`). If a level can be solved well without discovering the rule,
it does not measure rule discovery, which is the whole point of the benchmark.

## 2. The goal (proposed definition; confirm with Anssi and A1)

For the level's **new rule** (and ideally every active rule):

1. **Interaction required:** the optimal solution triggers the rule's effect (the engine's truth events show it, e.g.
   `slid`, `teleported`, `door_opened`, `hurt`; see `analysis/src/analysis/loader.py` `triggers_rule_event`).
2. **Avoidance is expensive:** the best plan that never interacts with the rule's objects is either impossible or at
   least `k ×` the optimal length (start with `k = 1.5`; tune it), **and** longer than the move budget, so an avoider
   scores 0 on that level, or close to it under the arena score (per level: `min(1, optimal / actions)` when solved).
3. Everything that holds today still holds: solvable, random walk < 2%, budget from slack, deterministic per seed,
   generation time about 0.5–2 s per game (the web "New game" button calls it live).

Measure, don't assume. Before changing anything, write a small audit that, for a sample of current games
(`dev`, `train-v1`, and a few `eval-v1` ids), reports per level: optimal length, avoid-optimal length (solve with the
rule's cells treated as blocked / the rule disabled, whichever fits that component), the ratio, whether the optimal path
triggers the rule, and the would-be avoider score. That audit is the "before" number and the evidence for the pitch.

## 3. Hard constraints

- **Frozen collections stay byte-identical.** `eval-v1`, `eval-v2`, `train-v1` and `dev` game ids must regenerate
  exactly as today; recorded traces and the leaderboard depend on it. Your stricter generation must be **opt-in**:
  a new generator version (e.g. a `GameSpec` field or a version tag in the game id), default off for existing
  collections. `python -m engine verify` on every frozen collection must stay green after your change.
- **Ownership:** `engine/` belongs to **A1 (FORGE)**. Proposed split (confirm with A1 via
  `coordination/requests/A7-to-A1-<slug>.md` before editing): A7 writes new files
  `engine/src/engine/generator/interaction.py` (the avoid-solver and the interaction checks) and
  `engine/tests/test_interaction.py`, and may add a **flag-gated** call in `generator/__init__.py` (`try_level`).
  Components (`engine/src/engine/components/`) and the solver stay A1's: ask A1 for any change there.
  You also own the audit script and its output under `analysis/`-free paths, e.g. `engine/tools/interaction_audit.py`
  (confirm the path with A1).
- **The engine is frozen except for bug fixes (PLAN.md §5 A1).** This work is a human-requested exception; it must not
  change behaviour for anything that is not opted in.
- No paid model calls. CPU only.
- Git: `git fetch && git rebase origin/main` before each commit; commit prefix `[A7]`; push with
  `git push origin HEAD:main`; never force-push; never commit `.env` or `data/runs/`.
  Other agents work in the same checkout on some machines: never `git stash` or reset their files.
- Status file `coordination/status/A7.md` (done / doing / blocked / need from humans), updated at each gate.

## 4. Where it pays off (decide with Anssi which to target)

1. **Web "New game" generator** (`POST /api/games/generate`, served by A2): new games use the stricter generator.
   Needs a server-side switch (request to A2) once the engine flag exists.
2. **Training data for post-training** (A1-20/21, A3 SFT v2 / RL): levels where the mechanic must be used teach
   discovery, not avoidance. Coordinate with A1 and A3 before they generate data.
3. **A new collection** (e.g. `eval-v3`, fresh seeds outside every existing range, frozen like the others) if the humans
   want a sweep on it before the 07:00 number lock. Model sweeps are A3/A4's and cost money: humans decide.
4. **The pitch:** the audit's before/after numbers ("on X% of current levels an avoider scores ≥ 0.8; with the new
   generator, 0%") are a strong, honest slide (tell A5).

## 5. Read / use

- `engine/src/engine/generator/` (`__init__.py`: `try_level`, `rule_matters`; `placement.py`: how components are
  placed; `curriculum.py`: which rule is new per level), `engine/src/engine/solver/` (`solve`, `replay_wins`,
  `random_walk_win_rate`), `engine/src/engine/components/` (one file per mechanic; `place()` and the truth events).
- `python -m engine --help` (render, verify, contact sheets); `from engine import make_game, GameSpec`.
- `analysis/src/analysis/explain.py` and `/api/derived/rules.json` (`failure_modes`) for the evidence of avoidance.
- Live server: `coordination/API_URL` (`/api/games/{id}` shows levels, rules, optimal paths).

## 6. Timing (Helsinki, PLAN.md §2)

| When | What |
|---|---|
| first hour | Questions answered; audit of current levels committed (the "before" numbers) |
| **H2 Sat 23:30** | Flag-gated stricter generator + tests; frozen collections verify unchanged; audit "after" numbers |
| Q2 overnight | Wire into whichever targets the humans chose (§4), via requests to A2 / A1 / A3 |
| **H4 Sun 07:00** | Numbers lock: no generator changes after this |

## 7. Ask at the start (minimum)

1. Anssi: is the definition in §2 right (interaction required + avoidance ≥ `k ×` optimal and over budget)? What `k`?
   New rule only, or every active rule on the level?
2. Anssi: which targets in §4 (web generator, training data, a new `eval-v3`, pitch numbers)?
3. A1: the file/ownership split in §3 and the opt-in mechanism (GameSpec field vs id version tag).
4. A1: for each component, what "avoiding it" means for the avoid-solver (block its cells, disable it, or other).
