# Project Submission Sheet (`docs/SUBMISSION.md`)

> Pre-filled submission reference matching `PLAN.md §7`, `docs/CHALLENGE.md`, and `coordination/JUDGING.md`.
> **Rule:** Every benchmark number below traces directly to `coordination/JUDGING.md`, `data/derived/*.json`, and `data/fixtures/derived/*.json` (verified by `python -m analysis check-claims`).

---

## Track & Metadata

- **Challenge / Track:** AfterQuery — *Build an RL Environment That Exposes Frontier Agent Failure Modes & Preserves Reward Integrity*
- **Repository:** `junction-2026` (`main`)
- **Live Server URL (`coordination/API_URL`):** Shared FastAPI + React 19 web app (`Play`, `Gallery`, `Replays`, `Compare`, `Live`, `Leaderboard`, `Insights`)
- **Official Harbor + OpenCode Judge One-Liner (`arena/HARBOR.md`, `arena/judge.sh`):**
  ```bash
  make judge                                     # eval-v2 game 1: reference 1.000, do-nothing 0.000, stop-early 0.125
  make judge MODEL=gemini/gemini-4-argon K=3     # + 3 OpenCode agent runs; any OpenCode selector works
  ```
  The agent phase can reach only the game (`http://localhost:8000/mcp`) and model APIs (egress allowlist); add another
  API host with `EXTRA="--allow-agent-host <host>"`.

---

## Short Pitch (Portal Summary — ~65 words)

We built a procedurally seeded 64×64 pixel RL game factory (runtime engine `0.6.0`) where agents receive zero prose rules, object colors permute per game (`skin_shuffle`), and hidden rules are introduced through a multi-level curriculum. Frozen `eval-v1` and `eval-v2` collections are graded against exact BFS shortest paths. The historical `eval-v2` snapshot below reports reference `1.000`, first-attempt humans `0.693`, Gemini 4 Argon `0.494`, Kimi K3.1 Pro `0.398`, and do-nothing `0.000`; see the dated snapshot caveat before quoting these results.

---

## How It Maps to the AfterQuery Judging Rubric (100 Points)

### 1. The Gap (30 pts)
- **Historical frozen eval-v2 snapshot** (difficulty 4, 8 levels, 3 Tier 3 rules per game), board built Sat 14.11 19:19 UTC from 1,006 runs. Raw runs and `data/derived/` are absent from this clone; figures below are copied from that recorded snapshot and have not been revalidated here:
  optimal **1.000**; first-attempt humans **0.693** (20 games, 150/160 levels, 75% full wins, CI 0.632-0.749);
  Gemini 4 Argon h1 **0.494** (7 games, CI 0.372-0.621); Gemini 3.1 Pro h2 **0.439**; Kimi K3.1 h2 **0.398**;
  Gemini 3.8 Flash h1 **0.028**; random / stop-early / do-nothing **0.000**.
- **Paired, same games:** humans ahead on every shared game: Argon 6/6, Flash 7/7, Gemini Pro h2 4/4, Kimi h2 4/4.
- **Honest caveats:** Gemini 4 Carbon's first finished eval-v2 game scored 0.789 (above the humans on that game;
  sweep still running). eval-v1 is the easy set (Gemini 4 models 0.82-0.93 on its game 1).
- **On the judges' harness (Harbor + OpenCode), eval-v2 game 1, k=3, 60-min cap** ([harbor/run-logs/](../harbor/run-logs/README.md)):
  reference 1.000; **Gemini 4 Carbon 0.743 / 0.767 / 0.777 (mean 0.762, 7/8 levels each)**; Gemini 3.8 Flash mean 0.322
  (quit early twice); Gemini 4 Argon 0.247 (OpenCode crashed on a Gemini 4 API error, agent-harness bug); stop-early
  0.125; do-nothing 0.000. Rerun: `make judge MODEL=<selector> K=3`.

### 2. Meaningful Difficulty (30 pts)
- **Full Pixel Observability, Zero Prose Leakage:** 15 mechanics across Tiers 1–2 plus 3 opt-in Tier 3 mechanics and 3 difficulty-4 mechanics (`no_reverse`, `checkpoints`, `pits`), rendered in `rules/img/all_rules.png` with HUD budget bar (`rows 0–1`) and level/inventory/health pips (`rows 3–4`).
- **Four Mathematical Fairness Proofs:** BFS shortest path (`optimal_moves`), rule-necessity ablation, `< 2%` random-walk win ceiling, and `ceil(optimal_moves × slack)` move budget.
- **Unseen Composition (`eval-v1`):** Holds out 6 unseen rule pairs (`(ice, teleporters)`, `(hazards, push_blocks)`, `(collect_all, one_way)`, `(phase_walls, plates_gates)`, `(cracked_floor, keys_doors)`, `(beacon_goal, twin)`) and disjoint visual palettes (`engine/src/engine/splits.py`).

### 3. Reward Integrity (25 pts)
- **Scoring Equation (`analysis/METRICS.md`):** `level_score(L) = min(1.0, optimal_moves(L) / actions_used(L))` if solved else `0.0`, averaged over all `levels_total` levels.
- **Verified Harbor & Arena Anti-Exploit Results:**
  - **Do-nothing (`harbor run -a nop` & `arena noop`):** **`0.000`** (`0/6` levels).
  - **Stop-early (`ORACLE_STOP_AFTER_LEVELS=1` / `=3` & `arena stop_early`):** **`0.167`** (`1/6` levels), **`0.500`** (`3/6` levels), and **`0.000`** before Level 1 completion — stopping early earns strictly the solved fraction and never inflates per-level averages.
  - **Reset farming:** `actions_used(L)` accumulates pre-reset actions plus `RESET` itself (`test_reward_integrity_and_reset_penalty`).
  - **Container Isolation:** In Harbor, the agent container cannot read `/evidence/score.json`, engine internals, or `optimal_path`; `game-server` exposes only `observe` and `act` over network MCP, and grading runs in a separate verifier container after stopping the agent.

### 4. Craft & Reproducibility (15 pts)
- **One-Command Harbor Export & Local Verification:** `make setup && make test`, `python -m arena harbor-export`, `harbor lint` clean, and `python -m analysis check-claims` (`7/7` analysis tests passing, `0` schema/claim errors).
- **Interactive Inspection Suite (`web/`):** Playable browser canvas (`/play`), level gallery with rotation-aware optimal paths (`/gallery`), side-by-side level comparison (`/compare`), live WebSocket wall (`/live`), compute/cost frontier (`/leaderboard`), and step-linked rule forensics (`/insights` → `/replay/<run_id>?step=<n>`).

---

## Architecture Summary (5 Workstreams)

| Agent | Package | Responsibility |
|---|---|---|
| **A1 (FORGE)** | `engine/` + `rules/` | Procedural gridworld generator (runtime engine `0.6.0`), BFS solver, frozen evaluation collections, hold-out splits, rule visuals |
| **A2 (GATEWAY)** | `server/` + `contracts/` | FastAPI server, crash-safe trace recorder, WebSocket live feed, published snapshot mode, JSON/OpenAPI contracts |
| **A3 (ARENA)** | `arena/` | Official Harbor task exporter (`harbor-export` + sidecar/verifier), `h1` multi-provider harness, baselines & sweeps |
| **A4 (STUDIO)** | `web/` (`overview`, `play`, `gallery`, `replay`, `compare`, `live`) | Dark pixel-ledger UI, human play canvas, multi-run comparison, Harbor Docker + OpenCode verification |
| **A5 (LENS)** | `analysis/`, `web/.../leaderboard\|insights`, `docs/` | Run hygiene & attribution, efficiency/hold-out metrics, rule-discovery matrix, `check-claims`, `eval-v2` auto-proposals, docs & deck |
