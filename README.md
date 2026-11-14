# Junction 2026 — Pixels-Only Inductive RL Curriculum (`junction-2026`)

> Built for the **AfterQuery @ Junction 2026** challenge: a procedurally seeded 64×64 pixel grid factory where AI agents and humans discover hidden mechanics through interaction under strict move budgets — with zero prose instructions, per-game color permutation (`skin_shuffle`), BFS-verified solvability, Harbor sidecar isolation, and exploit-resistant action-efficiency scoring.

![All 18 Composable Engine Mechanics (6×6 Teaching Frames)](rules/img/all_rules.png)

---

## Official Judge Evaluation: Harbor + OpenCode over MCP (`arena/HARBOR.md`)

Judges evaluate agents through **Harbor** (`harbor==0.26.0`) with Docker Compose sidecar isolation: the game server runs inside a separate `game-server` container exposing **only** `observe()` and `act()` over Streamable-HTTP MCP (`http://game-server:8000/mcp`), and the reward file (`/evidence/score.json`) is graded in a separate verifier container after the agent container stops.

### 0. Fresh-Clone Setup (Python 3.11+ & Docker)

```bash
git clone <repo> junction-2026 && cd junction-2026
make setup && . .venv/bin/activate      # creates .venv with engine, server, arena, analysis
uv tool install harbor==0.26.0          # Harbor CLI (or: pipx install harbor==0.26.0); Docker must be running
```

### 1. One-Command Eval & Reward-Integrity Baselines (`oracle`, `nop`, `stop-early`)

The frozen evaluation tasks are already committed at `harbor/eval-v1/` (`30` tasks, `harbor lint` clean) and `harbor/eval-v2/` (`30` tasks, difficulty 4), so judges can run directly without re-exporting:

```bash
# Run directly on committed frozen eval-v1 task 1 (or re-export via: python -m arena harbor-export --collection eval-v1 --out /tmp/junction-harbor --first 3)
TASK=harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4
harbor lint "$TASK"

# 1) Reference ceiling (BFS optimal_path -> reward 1.000)
harbor run -p "$TASK" -a oracle

# 2) Do-nothing baseline (0 actions -> reward 0.000)
harbor run -p "$TASK" -a nop

# 3) Stop-early baseline (solves Level 1 only, stops -> reward 1/6 = 0.167)
harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1
```

### 2. Run OpenCode + Nemotron 3.5 Super VL (`k=3` Rubric Runs)

```bash
set -a; . ./.env; set +a   # requires NVIDIA_VERDA_INFERENCE_KEY in .env
harbor run -p "$TASK" -a opencode -m verda-nemotron/nemotron-3.5-super-vl \
  --ak "opencode_config=$(python3 -c 'import json;print(json.dumps(json.load(open("arena/opencode-nemotron.json"))))')" \
  --ae 'NVIDIA_VERDA_INFERENCE_KEY=${NVIDIA_VERDA_INFERENCE_KEY}' \
  -k 3 -n 1
```

### Verified Harbor Rubric Results (`gridworld-s1000-d1-l6-9b1065f8`, Docker 29.8.1 + Harbor 0.26.0)

| Run | Harbor Command | Actions | Levels | Reward |
|---|---|---:|---:|---:|
| **Reference (`oracle`)** | `harbor run -p "$TASK" -a oracle` | 92 | 6 / 6 | **1.000** |
| **Stop-early (L3)** | `harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=3` | 45 | 3 / 6 | **0.500** |
| **Stop-early (L1)** | `harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1` | 13 | 1 / 6 | **0.167** |
| **OpenCode + Nemotron (`k=3`)** | `-a opencode -m verda-nemotron/nemotron-3.5-super-vl` | 155 / 135 / 227 | 1/6 each | **0.067 mean** (`0.020`, `0.094`, `0.087`) |
| **Do-nothing (`nop`)** | `harbor run -p "$TASK" -a nop` | 0 | 0 / 6 | **0.000** |

> *Note:* `python -m server mcp` is retained strictly for interactive local dev/demo inspection; official evaluation runs exclusively through `arena harbor-export` + `harbor run` ([arena/HARBOR.md](arena/HARBOR.md), [coordination/JUDGING.md](coordination/JUDGING.md)).

---

## Local Test Suite, Claim Verification & Web Build

```bash
# Unix / macOS / Linux
make setup && make test
python -m analysis build --fixtures
python -m analysis check-claims --derived data/fixtures/derived

# Sync live runs from shared server and rebuild derived analytics
python -m analysis sync
python -m analysis build --write-proposals
python -m analysis check-claims --derived data/derived

# Build the React 19 + Observable Plot web frontend
cd web && npm install && npm run typecheck && npm run build
```

---

## What Makes This Environment Meaningful & Exploit-Resistant

1. **Zero Text Hints + Per-Game `skin_shuffle` (`engine 0.5.0`, [rules/CATALOG.md](rules/CATALOG.md)):**
   Agents observe only a `64×64` frame of palette indices `0..15` ([contracts/palette.json](contracts/palette.json)) and `available_actions` (`RESET`, `ACTION1..4`, plus `ACTION5` wait when active). Colors and non-directional glyphs permute per game seed.
   - **HUD (`rows 0–1`):** move-budget bar shrinking per step.
   - **HUD (`rows 3–4`):** level progress pips + held-key / health / gem / stamina state indicators.
   - **Playfield (`rows 6–63`):** **15 live mechanics** across Tiers 0–2 (`walls`, `goal`, `move_budget`, `keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `ice`, `one_way`, `collect_all`, `phase_walls`, `rotation`, `remap`, `twin`, `stamina`, `cracked_floor`, `beacon_goal` — 3 base + 15 composable rules) plus **3 opt-in Tier-3 mechanics** (`conveyors`, `enemies`, `gravity`) ready for `eval-v2`.
2. **Four Generation-Time Fairness Proofs:**
   Every level passes exact BFS shortest-path verification (`optimal_moves`, `optimal_path`), rule-necessity ablation (removing any active rule alters optimal path or solvability), bounded budget slack (`ceil(optimal_moves × slack)`), and `< 2%` random-walk win rejection. Held-out `eval-v1` adds **unseen rule pairs** and **held-out visual skins** (`engine/src/engine/splits.py`).
3. **Action-Efficiency Reward Integrity ([analysis/METRICS.md](analysis/METRICS.md)):**
   $$\text{level\_score}(L) = \min\!\left(1.0,\; \frac{\text{optimal\_moves}(L)}{\text{actions\_used}(L)}\right) \text{ if solved else } 0.0$$
   - `noop` and `stop_early` score **`0.000`**; denominator always spans `1..levels_total`.
   - `actions_used(L)` includes all actions taken before `RESET` plus `RESET` itself — reset farming strictly lowers efficiency.
   - `Truth` (`optimal_moves`, `events`, `active_rules`, `new_rule`) never enters LLM prompts or Harbor MCP responses.

---

## Live Multi-Model Benchmark Results (`dev` Split, Engine `0.5.0`, `h1` Harness)

Synced from the shared server (`67` clean benchmark runs after filtering practice `anonymous`/`test` sessions, `smoke-*` checks, and tunnel timeouts) and verified by `python -m analysis check-claims --derived data/derived` (`0` errors):

| Player | Modality | Games | Levels Solved | Action-Eff. Score | No-Effect Rate | Resets | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| **`Optimal`** | baseline | 4 | 24 / 24 (`100.0%`) | **1.000** | 6.0% | 0 | Exact BFS `optimal_path` (`WAIT` at `phase_walls`) |
| **`Human`** | `image` | 10 | 40 / 60 (`66.7%`) | **0.578** | 6.9% | 3 | First-attempt human play (`40%` full-game win; `0.795` on `eval-v1`) |
| **`Kimi K3.1 Pro (Verda)`** | `image+rle` | 8 | 25 / 48 (`52.1%`) | **0.374** | 7.6% | 13 | Frontier VLM (`RHAE = 0.647` vs human; best run `5/6` lvls) |
| **`Nemotron 3.5 Super VL`** | `image+rle` | 8 | 6 / 48 (`12.5%`) | **0.061** | 76.8% | 28 | 120B MoE open VLM |
| **`DeepSeek V3.2`** | `rle` | 8 | 0 / 48 (`0.0%`) | **0.000** | 55.1% | 67 | 671B MoE text-only (`$0.069/game`) |
| **`gpt-oss-120b`** | `rle` | 8 | 0 / 48 (`0.0%`) | **0.000** | 65.8% | 42 | 120B MoE text-only (`$0.193/game`) |
| **`Random` / `Stop Early` / `Noop`** | baseline | 20 | 0 / 120 (`0.0%`) | **0.000** | — | 30 / 0 / 0 | Verified zero-exploit baselines |

*(Offline CI baseline in `data/fixtures/derived/leaderboard.json` is also committed and verified via `python -m analysis check-claims --derived data/fixtures/derived`.)*

---

## Repository Structure

| Directory | Role | Key Files |
|---|---|---|
| `contracts/` | Shared JSON schemas, 16-color palette, OpenAPI, engine protocol | [contracts/derived.schema.json](contracts/derived.schema.json), [contracts/trace.schema.json](contracts/trace.schema.json), [contracts/openapi.yaml](contracts/openapi.yaml) |
| `engine/` | Seeded curriculum generator, 18 rule components, BFS verifier, hold-out splits | [rules/CATALOG.md](rules/CATALOG.md), [engine/src/engine/splits.py](engine/src/engine/splits.py) |
| `server/` | FastAPI host, crash-safe trace recorder, WS `/api/live`, published snapshot mode | [server/src/server/app.py](server/src/server/app.py) |
| `arena/` | Harbor task exporter (`harbor-export`), `h1` LLM harness, baselines, sweeps | [arena/HARBOR.md](arena/HARBOR.md), [arena/models.yaml](arena/models.yaml), [arena/opencode-nemotron.json](arena/opencode-nemotron.json) |
| `analysis/` | Run hygiene, attribution, rule-discovery matrix, sync, claim-check, auto-proposals | [analysis/METRICS.md](analysis/METRICS.md), [analysis/tests/test_analysis.py](analysis/tests/test_analysis.py) |
| `web/` | React 19 + Observable Plot UI (`/`, `/play`, `/gallery`, `/replay`, `/compare`, `/live`, `/leaderboard`, `/insights`) | [web/DESIGN.md](web/DESIGN.md), [web/screenshots/README.md](web/screenshots/README.md) |
| `docs/` | Pitch, demo script, submission sheet, Q&A prep, standalone HTML deck | [docs/SUBMISSION.md](docs/SUBMISSION.md), [docs/QA_PREP.md](docs/QA_PREP.md), [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md), [docs/PITCH.md](docs/PITCH.md), [docs/deck/index.html](docs/deck/index.html) |
| `rules/proposals/` | Tier-2/3 specs + automated `eval-v2` failure-driven proposals | [rules/proposals/auto-04-eval-v2-tier3-drift-and-timing.md](rules/proposals/auto-04-eval-v2-tier3-drift-and-timing.md) |
