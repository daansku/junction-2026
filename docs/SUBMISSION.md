# Project Submission Sheet (`docs/SUBMISSION.md`)

> Pre-filled submission reference matching `PLAN.md §7`, `docs/CHALLENGE.md`, and `coordination/JUDGING.md`.
> **Rule:** Every benchmark number below traces directly to `coordination/JUDGING.md`, `data/derived/*.json`, and `data/fixtures/derived/*.json` (verified by `python -m analysis check-claims`).

---

## Track & Metadata

- **Challenge / Track:** AfterQuery — *Build an RL Environment That Exposes Frontier Agent Failure Modes & Preserves Reward Integrity*
- **Repository:** `junction-2026` (`main`)
- **Live Server URL (`coordination/API_URL`):** Shared FastAPI + React 19 web app (`Play`, `Gallery`, `Replays`, `Compare`, `Live`, `Leaderboard`, `Insights`)
- **Official Harbor + OpenCode Judge One-Liner (`arena/HARBOR.md`):**
  ```bash
  python -m arena harbor-export --collection eval-v1 --out /tmp/junction-harbor --first 3 && \
    TASK=$(ls -d /tmp/junction-harbor/gridworld-* | head -1) && \
    harbor run -p "$TASK" -a oracle && \
    harbor run -p "$TASK" -a nop && \
    harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1
  ```
- **OpenCode + Nemotron `k=3` Harbor Rerun:**
  ```bash
  set -a; . ./.env; set +a
  harbor run -p "$TASK" -a opencode -m verda-nemotron/nemotron-3.5-super-vl \
    --ak "opencode_config=$(python3 -c 'import json;print(json.dumps(json.load(open("arena/opencode-nemotron.json"))))')" \
    --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' -k 3 -n 1
  ```

---

## Short Pitch (Portal Summary — ~65 words)

We built a procedurally seeded 64×64 pixel RL game factory (`engine 0.5.0`, 15 live + 3 Tier-3 mechanics) where agents receive zero prose rules, object colors permute per game (`skin_shuffle`), and hidden rules are introduced one per level before multi-rule and held-out pair exams (`eval-v1`). Graded inside isolated Harbor MCP sidecars against exact BFS shortest paths, reference achieves `1.000`, humans `0.578`, Kimi K3.1 Pro `0.374`, OpenCode+Nemotron `0.067`, and `noop` `0.000`.

---

## How It Maps to the AfterQuery Judging Rubric (100 Points)

### 1. The Gap (30 pts)
- **On the Judges' Own Harness (`Harbor 0.26.0 + OpenCode`, `gridworld-s1000-d1-l6-9b1065f8`, 6 levels, 92 optimal actions):**
  - **Reference (`harbor run -a oracle`):** **`1.000`** (`6/6` levels, `92` actions).
  - **OpenCode + Nemotron 3.5 Super VL (`k=3` rubric runs, 30-min cap):** **`0.020`** (`155` act, `1/6`), **`0.094`** (`135` act, `1/6`), **`0.087`** (`227` act, `1/6`) → **mean `0.067`** (plus `0.113` / `2/6` levels in 15-min run).
- **Multi-Model Arena Sweep (`dev` split, Engine `0.5.0`, `67` clean runs, `data/derived/leaderboard.json`):**
  - **BFS Optimal (`optimal`):** **`1.000`** (`24/24` levels, `100.0%`).
  - **First-Attempt Human (`human`):** **`0.578`** on `dev` (`40/60` levels, `66.7%`, `40.0%` full-game win rate) and **`0.795`** on `eval-v1` (`6/6`).
  - **Kimi K3.1 Pro (`[image, rle]`):** **`0.374`** (`25/48` levels, `52.1%`, `0%` full-game win, `RHAE = 0.647` vs human).
  - **Nemotron 3.5 Super VL (`[image, rle]`):** **`0.061`** (`6/48` levels, `12.5%`, `76.8%` no-effect rate).
  - **DeepSeek V3.2 & `gpt-oss-120b` (`[rle]` text-only):** **`0.000`** (`0/96` levels solved despite lossless 64×64 RLE grids — exposing a stark 2D spatial vision gap).

### 2. Meaningful Difficulty (30 pts)
- **Full Pixel Observability, Zero Prose Leakage:** 15 live composable rules across Tiers 0–2 (`keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `ice`, `one_way`, `collect_all`, `phase_walls`, `rotation`, `remap`, `twin`, `stamina`, `cracked_floor`, `beacon_goal`) plus 3 opt-in Tier-3 mechanics (`conveyors`, `enemies`, `gravity`), rendered in `rules/img/all_rules.png` with HUD budget bar (`rows 0–1`) and level/inventory/health pips (`rows 3–4`).
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
| **A1 (FORGE)** | `engine/` + `rules/` | Procedural gridworld generator (`0.5.0`), 18 composable mechanics, BFS solver, `eval-v1` hold-out splits, rule visuals |
| **A2 (GATEWAY)** | `server/` + `contracts/` | FastAPI server, crash-safe trace recorder, WebSocket live feed, published snapshot mode, JSON/OpenAPI contracts |
| **A3 (ARENA)** | `arena/` | Official Harbor task exporter (`harbor-export` + sidecar/verifier), `h1` multi-provider harness, baselines & sweeps |
| **A4 (STUDIO)** | `web/` (`overview`, `play`, `gallery`, `replay`, `compare`, `live`) | Dark pixel-ledger UI, human play canvas, multi-run comparison, Harbor Docker + OpenCode verification |
| **A5 (LENS)** | `analysis/`, `web/.../leaderboard\|insights`, `docs/` | Run hygiene & attribution, efficiency/hold-out metrics, rule-discovery matrix, `check-claims`, `eval-v2` auto-proposals, docs & deck |
