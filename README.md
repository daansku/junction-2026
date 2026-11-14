# Junction 2026 — Pixels-Only Inductive RL Curriculum (`junction-2026`)

> Built for the **AfterQuery @ Junction 2026** challenge: a procedurally seeded 64×64 pixel grid factory where AI agents and humans discover hidden mechanics through interaction under strict move budgets — with zero prose instructions, per-game color permutation (`skin_shuffle`), BFS-verified solvability, Harbor sidecar isolation, and exploit-resistant action-efficiency scoring.

![All 18 Composable Engine Mechanics (6×6 Teaching Frames)](rules/img/all_rules.png)

---

## Official Judge Evaluation: Harbor + OpenCode over MCP (`arena/HARBOR.md`)

Judges evaluate agents through **Harbor** (`harbor==0.26.0`) with Docker Compose sidecar isolation: the game server runs inside a separate `game-server` container exposing **only** `observe()` and `act()` over Streamable-HTTP MCP (`http://localhost:8000/mcp`; the agent phase can reach only the game and model APIs, see [arena/HARBOR.md](arena/HARBOR.md) "Network"), and the reward file (`/evidence/score.json`) is graded in a separate verifier container after the agent container stops.

### 0. Fresh-Clone Setup (Python 3.11+ & Docker)

```bash
git clone <repo> junction-2026 && cd junction-2026
make setup && . .venv/bin/activate      # creates .venv with engine, server, arena, analysis
uv tool install harbor==0.26.0          # Harbor CLI (or: pipx install harbor==0.26.0); Docker must be running
```

### 1. One Command: Reference, Do-Nothing, Stop-Early and Agent Runs

The frozen evaluation tasks are committed at `harbor/eval-v2/` (`30` tasks, difficulty 4, 8 levels, 3 unseen rules per game: **the judging set**) and `harbor/eval-v1/` (`30` tasks, difficulty 1-3, 6 levels: easier, frontier models nearly solve it). `harbor lint` clean; no re-export needed.

```bash
make judge                                          # eval-v2 game 1: reference + do-nothing + stop-early (no model cost)
make judge MODEL=gemini/gemini-4-argon K=3          # + 3 OpenCode agent runs (60-min cap each)
make judge TASK=harbor/eval-v2/<task> MODEL=anthropic/claude-sonnet-5-5 K=3
```

`MODEL` is an OpenCode selector: `anthropic/<model>`, `gemini/<model>`, `openai/<model>`, or one registered in [arena/opencode-models.json](arena/opencode-models.json) (`verda-kimi/kimi-k3-1-pro`, `verda-nemotron/nemotron-3.5-super-vl`, `featherless/<org>/<model>`). Keys come from `.env` ([coordination/KEYS.md](coordination/KEYS.md)). The agent can reach only the game and the model APIs in each task's egress allowlist; for another API add `EXTRA="--allow-agent-host <host>"` ([arena/HARBOR.md](arena/HARBOR.md), "Network"). `make judge` ([arena/judge.sh](arena/judge.sh)) prints a summary table at the end.

The same runs by hand:

```bash
TASK=harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e
harbor run -p "$TASK" -a oracle                                    # reference: BFS optimal path -> 1.000
harbor run -p "$TASK" -a nop                                       # do-nothing -> 0.000
harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1    # stop-early after level 1 -> 1/8 = 0.125
set -a; . ./.env; set +a
harbor run -p "$TASK" -a opencode -m gemini/gemini-4-argon -k 3 -n 1 \
  --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}'              # Gemini: OpenCode reads this name, not GEMINI_API_KEY
```

### Verified Harbor Results (Docker 29.8.1 + Harbor 0.26.0)

| Run | Task | Actions | Levels | Reward |
|---|---|---:|---:|---:|
| **Reference (`oracle`)** | eval-v2 game 1 (`s910000`) | 187 | 8 / 8 | **1.000** |
| **Stop-early (L1)** | eval-v2 game 1 | 31 | 1 / 8 | **0.125** |
| **Do-nothing (`nop`)** | eval-v2 game 1 | 0 | 0 / 8 | **0.000** |
| **Reference (`oracle`)** | eval-v1 game 1 (`s900000`) | 86 | 6 / 6 | **1.000** |
| **OpenCode + Nemotron (`k=3`, 30-min cap)** | dev game `s1000` | 155 / 135 / 227 | 1/6 each | **0.067 mean** (`0.020`, `0.094`, `0.087`) |

Every model in [arena/HARBOR.md](arena/HARBOR.md) ("Other models through OpenCode") plays through Harbor + OpenCode (smoke runs: Claude Haiku 5.5, Kimi K3.1, Gemini 4 Argon / Carbon, Gemini 3.8 Flash, Nemotron, DeepSeek V3.2, GLM 5.3). Reward-exploit red team (10 attacks from the agent's seat, all 0.0 or blocked): [coordination/JUDGING.md](coordination/JUDGING.md).

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
   Agents observe only a `64×64` frame of palette indices `0..15` ([contracts/palette.json](contracts/palette.json)) and `available_actions` (`RESET`, `ACTION1..4`; `ACTION5` interact is listed only in games that use it, none in the frozen sets; phase walls advance with every counted action). Colors and non-directional glyphs permute per game seed.
   - **HUD (`rows 0–1`):** move-budget bar shrinking per step.
   - **HUD (`rows 3–4`):** level progress pips + held-key / health / gem / stamina state indicators.
   - **Playfield (`rows 6–63`):** **15 live mechanics** across Tiers 0–2 (`walls`, `goal`, `move_budget`, `keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `ice`, `one_way`, `collect_all`, `phase_walls`, `rotation`, `remap`, `twin`, `stamina`, `cracked_floor`, `beacon_goal` — 3 base + 15 composable rules) plus **3 opt-in Tier-3 mechanics** (`conveyors`, `enemies`, `gravity`) ready for `eval-v2`.
2. **Four Generation-Time Fairness Proofs:**
   Every level passes exact BFS shortest-path verification (`optimal_moves`, `optimal_path`), rule-necessity ablation (removing any active rule alters optimal path or solvability), bounded budget slack (`ceil(optimal_moves × slack)`), and `< 2%` random-walk win rejection. Held-out `eval-v1` adds **unseen rule pairs** and **held-out visual skins** (`engine/src/engine/splits.py`).
3. **Action-Efficiency Reward Integrity ([analysis/METRICS.md](analysis/METRICS.md)):**
   $$\text{level\_score}(L) = \min\!\left(1.0,\; \frac{\text{optimal\_moves}(L)}{\text{actions\_used}(L)}\right) \text{ if solved else } 0.0$$
   - Do-nothing scores **`0.000`**; stopping early earns only the levels solved (Harbor oracle stopped after level 1: `1/8 = 0.125` on eval-v2), and the arena `stop_early` baseline (stops before finishing level 1) scores `0.000`. The denominator always spans `1..levels_total`.
   - `actions_used(L)` includes all actions taken before `RESET` plus `RESET` itself — reset farming strictly lowers efficiency.
   - `Truth` (`optimal_moves`, `events`, `active_rules`, `new_rule`) never enters LLM prompts or Harbor MCP responses.

---

## The Gap: Frozen `eval-v2` (Difficulty 4, `h1` / `h2` Harnesses)

Board built Sat 14.11 19:19 UTC from the shared server's `1,006` runs (`python -m analysis sync && python -m analysis build`; practice, smoke and aborted runs filtered). Score = mean over levels of `min(1, optimal / actions)` for solved levels, 0 otherwise; humans play each game once (first attempt).

| Player | Harness | Games | Levels Solved | Full Wins | Score | 95% CI |
|---|---|---:|---:|---:|---:|---|
| **Optimal (BFS)** | - | 20 | 160 / 160 | 100% | **1.000** | - |
| **Human (first attempt)** | browser | 20 | 150 / 160 | 75% | **0.693** | 0.632-0.749 |
| **Gemini 4 Argon** | h1 | 7 | 36 / 56 | 14% | **0.494** | 0.372-0.621 |
| **Gemini 3.1 Pro** | h2 | 4 | 20 / 32 | 0% | **0.439** | 0.242-0.636 |
| **Kimi K3.1 Pro** | h2 | 4 | 20 / 32 | 0% | **0.398** | 0.150-0.590 |
| **Gemini 3.8 Flash** | h1 | 8 | 3 / 64 | 0% | **0.028** | 0.004-0.060 |
| **Random / Stop-early / Do-nothing** | - | 20 each | 0 | 0% | **0.000** | - |

**Paired on the same eval-v2 games (human vs model, per game):** humans score higher on every shared game for Gemini 4 Argon (6 / 6; 0.656 vs 0.442), Gemini 3.8 Flash (7 / 7), Gemini 3.1 Pro h2 (4 / 4; 0.661 vs 0.439) and Kimi K3.1 h2 (4 / 4; 0.661 vs 0.398).

*Still running at build time (single games, not yet a row to trust):* Gemini 4 Carbon finished 1 eval-v2 game at **0.789** (8/8, above the humans' 0.635 on that game); Claude Sonnet 5.5 1 game at 0.044. The Gemini 4 sweep over all 30 eval-v2 games is in progress; rebuild before quoting.

**eval-v1 is the easy set:** on the one eval-v1 game they played, Gemini 4 Carbon / Argon / Hydrogen score 0.925 / 0.900 / 0.820, near the optimum and above humans. Use eval-v2 for the gap.

h1 = one fresh request per turn (notes + last 12 actions + frame); h2 = how labs benchmark (full history, reasoning kept, native tool calls, high effort). OpenCode in Harbor is a third harness (bash + code allowed); its numbers come from `make judge`.

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
