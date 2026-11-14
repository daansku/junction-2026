# Junction 2026 — Pixels-Only Inductive RL Environment (`junction-2026`)

> Built for the **AfterQuery @ Junction 2026** challenge: an interactive 64×64 pixel grid curriculum where AI agents and humans discover hidden mechanics through interaction under strict move budgets — with zero prose instructions, BFS-verified solvability, step-accurate rule discovery telemetry, and exploit-resistant action-efficiency scoring.

---

## One-Command Verification & Local Evaluation

### Unix / macOS / Git Bash (`Makefile`)

```bash
make setup
make test
python -m analysis build --fixtures --write-proposals
python -m analysis check-claims --derived data/fixtures/derived
```

### Windows PowerShell (Global Python or Active `.venv`)

```powershell
$env:PYTHONPATH = "analysis/src"
python -m unittest discover -s analysis/tests -v
python -m analysis build --fixtures --write-proposals
python -m analysis check-claims --derived data/fixtures/derived
```

Build the frontend UI:

```bash
cd web
npm install
npm run typecheck
npm run build
```

Run the server and connect **Harbor + OpenCode over MCP**:

```bash
make server PORT=8000
# In a second terminal (or pass --api <shared_url_from_coordination/API_URL>):
python -m server mcp --api http://localhost:8000
```

---

## What Makes This Environment Meaningful & Exploit-Resistant

1. **Zero Text Hints + Per-Game `skin_shuffle` (`engine/`):**
   Agents observe only a `64×64` frame of integer palette indices `0..15` ([palette.json](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/contracts/palette.json)) and `available_actions` (`RESET`, `ACTION1..4`). Object colors permute per game seed so memorizing color-rule heuristics fails.
   - **HUD (`rows 0–1`):** move-budget bar shrinking per step.
   - **HUD (`rows 3–4`):** level progress pips + component state indicators (keys/health).
   - **Playfield (`rows 6–63`):** seven live composable mechanics ([rules/CATALOG.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/rules/CATALOG.md)): `keys_doors`, `plates_gates`, `teleporters`, `hazards`, `push_blocks`, `one_way`, `ice`.
2. **Every Level is Proven Fair at Generation Time:**
   Every level has a verified BFS shortest path (`optimal_moves`, `optimal_path`), a rule-necessity check proving every active rule alters the optimal path or solvability, bounded budget slack (`ceil(optimal_moves × slack)`), and `< 2%` random-walk win probability.
3. **Action-Efficiency Reward Integrity ([analysis/METRICS.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/analysis/METRICS.md)):**
   $$\text{level\_score}(L) = \min\!\left(1.0,\; \frac{\text{optimal\_moves}(L)}{\text{actions\_used}(L)}\right) \text{ if solved else } 0.0$$
   - `noop` and `stop_early` score **`0.000`** (denominator always spans `1..levels_total`).
   - `actions_used(L)` includes actions before `RESET` plus `RESET` itself — reset farming strictly lowers efficiency.
   - `Truth` (`optimal_moves`, `events`, `active_rules`, `new_rule`) never enters LLM prompts or MCP tool responses.

---

## Verified Fixture Baseline Results (`data/fixtures/derived/leaderboard.json`)

Generated deterministically by `python -m analysis build --fixtures --write-proposals` and verified by `python -m analysis check-claims --derived data/fixtures/derived` (`0` errors):

| Player | Kind | Games | Levels Solved | Score (Action Eff.) | No-Effect Rate | Resets | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| `Optimal` | `baseline` | 3 | 15 / 15 | **1.000** | 0.0% | 0 | Exact BFS `optimal_path` |
| `Mock Model (medium)` | `model` | 1 | 2 / 6 | **0.252** | 3.3% | 1 | `fixture-run-0001` (`5/7` L1, `16/20` L2, `0` L3–L6) |
| `Random` | `baseline` | 3 | 1 / 15 | **0.008** | 32.2% | 31 | Exhausts 200-action budget |
| `Stop Early` | `baseline` | 3 | 0 / 15 | **0.000** | 40.0% | 0 | Aborts after 5 moves |
| `Noop` | `baseline` | 3 | 0 / 15 | **0.000** | — | 0 | Zero actions taken |

To pull live sweep & human traces from the shared server and rebuild derived analytics:

```bash
python -m analysis sync --data-dir ~/junction-data
python -m analysis build --data-dir ~/junction-data --with-fixture-baselines --write-proposals
python -m analysis check-claims --derived ~/junction-data/derived
```

---

## Repository Structure

| Directory | Role | Key Files |
|---|---|---|
| `contracts/` | Shared schemas, palette, OpenAPI, engine protocol | [derived.schema.json](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/contracts/derived.schema.json), [trace.schema.json](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/contracts/trace.schema.json), [openapi.yaml](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/contracts/openapi.yaml) |
| `engine/` | Procedural game generator, components, BFS verifier | [rules/CATALOG.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/rules/CATALOG.md) |
| `server/` | FastAPI host, trace recorder, WS live feed, MCP stdio server | [app.py](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/server/src/server/app.py), [fake_engine.py](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/server/src/server/fake_engine.py) |
| `arena/` | LLM agent loop (`h1`), baselines, provider adapters, sweeps | [models.yaml](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/arena/models.yaml), [agent_loop.py](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/arena/src/arena/agent_loop.py), [baselines.py](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/arena/src/arena/baselines.py) |
| `analysis/` | Score aggregation, rule-discovery matrix, sync, claim-check | [METRICS.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/analysis/METRICS.md), [test_analysis.py](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/analysis/tests/test_analysis.py) |
| `web/` | React 19 + Observable Plot UI (`/play`, `/gallery`, `/replay`, `/leaderboard`, `/insights`) | [DESIGN.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/web/DESIGN.md), [LeaderboardPage.tsx](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/web/src/features/leaderboard/LeaderboardPage.tsx), [InsightsPage.tsx](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/web/src/features/insights/InsightsPage.tsx) |
| `docs/` | Pitch, demo script, submission, Q&A, HTML presentation deck | [PITCH.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/docs/PITCH.md), [DEMO_SCRIPT.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/docs/DEMO_SCRIPT.md), [SUBMISSION.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/docs/SUBMISSION.md), [QA_PREP.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/docs/QA_PREP.md), [index.html](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/docs/deck/index.html) |
| `rules/proposals/` | Tier-2 rule specs + automated `eval-v2` failure-driven proposals | `a5-*.md`, `auto-*.md` |

---

## Live Deployment & Team

- **Shared Server Address:** `coordination/API_URL` (`server` + static built `web/dist`).
- **Evaluation Specs & Research:** [docs/research/DIGEST.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/docs/research/DIGEST.md) · [docs/CHALLENGE.md](file:///C:/Users/Anton/port_hackathon_2026/verItAs/New%20version/junction-2026/docs/CHALLENGE.md).
