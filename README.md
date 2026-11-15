# Junction 2026 — Game Factory: can an agent figure out a game nobody explained?

An environment for the **AfterQuery @ Junction 2026** challenge. One command runs the judging protocol: `make judge` ([below](#1-one-command-reference-do-nothing-stop-early-and-agent-runs)).

## In plain words

**What the agent has to do.** It plays a small video game it has never seen. Each turn it gets the screen (a 64×64 picture, also given as a grid of colour numbers) and chooses a move: up, down, left, right, or RESET to restart the level. Nobody tells it the goal, the rules or what the colours mean; it finds out by moving and watching what changes. A game has several levels (8 in the judging set). Level 1 is a plain maze; each following level adds one new hidden mechanic, such as ice you slide across, plates that open or close gates elsewhere, keys and doors, a tile that turns the whole map, or a second figure that copies your moves; the last level combines them. Every level has a move budget, shown as the bar at the top of the screen.

**Why it is hard.** Playing well means running a small experiment loop: guess what a new object does, test the guess in as few moves as possible, remember what you learned, plan a route that uses it, and notice when the next level changes the rules again. Everything needed is on screen, and every level is checked solvable by exact search (and every mechanic in it matters for the solution), so a failure comes from the agent's own decisions, not from hidden information or trick wording. The typical frontier-model mistakes are repeating moves that change nothing (walking into walls), holding on to a wrong guess about a rule, and missing what a new level introduced. Games are generated from a seed, so there is an endless supply of fresh games no model has seen in training.

**How it is scored.** The reward is **efficiency**. For each level: if solved, the shortest possible number of moves divided by the moves used (at most 1); if not solved, 0. A game's efficiency is the average over all its levels, and every action counts, RESET included. So the shortest-path reference run gets **1.000**, doing nothing **0.000**, and stopping after level 1 of 8 **0.125**. This is the number Harbor writes to `reward.txt` and the RL reward. It is computed inside the game container and graded in a separate verifier container the agent cannot reach; ten reward-exploit attempts from the agent's seat all scored 0 or were blocked ([docs/JUDGING.md](docs/JUDGING.md)). **Leaderboards rank by completion first:** share of games won (all levels finished), then levels solved, with efficiency as the tiebreak ([analysis/METRICS.md](analysis/METRICS.md)).

**Why this setting, and what an agent can learn here.** It exercises four of the challenge's starting points at once: exploring an unfamiliar system, planning several steps ahead, managing a limited budget, and adapting when new information arrives (in the spirit of ARC-AGI-3). A separate training split (different seeds, some rule combinations held out for evaluation) makes it a training environment as well as a test; we post-trained a small open model (Qwen3.5-9B) on it, see [posttrain/](posttrain/) and [bench/](bench/).

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
make judge MODEL=gemini/gemini-4-argon K=3          # + 3 OpenCode agent runs in parallel (2 h cap each)
make judge TASK=harbor/eval-v2/<task> MODEL=anthropic/claude-sonnet-5-5 K=3
```

`MODEL` is an OpenCode selector: `anthropic/<model>`, `gemini/<model>`, `openai/<model>`, or one registered in [arena/opencode-models.json](arena/opencode-models.json) (`verda-kimi/kimi-k3-1-pro`, `verda-nemotron/nemotron-3.5-super-vl`, `featherless/<org>/<model>`). Keys come from `.env` ([docs/KEYS.md](docs/KEYS.md)). The agent can reach only the game and the model APIs in each task's egress allowlist; for another API add `EXTRA="--allow-agent-host <host>"` ([arena/HARBOR.md](arena/HARBOR.md), "Network"). `make judge` ([arena/judge.sh](arena/judge.sh)) prints a summary table at the end.

The same runs by hand:

```bash
TASK=harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e
harbor run -p "$TASK" -a oracle                                    # reference: BFS optimal path -> 1.000
harbor run -p "$TASK" -a nop                                       # do-nothing -> 0.000
harbor run -p "$TASK" -a oracle --ae ORACLE_STOP_AFTER_LEVELS=1    # stop-early after level 1 -> 1/8 = 0.125
set -a; . ./.env; set +a
harbor run -p "$TASK" -a opencode -m gemini/gemini-4-argon -k 3 -n 3 \
  --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}'              # Gemini: OpenCode reads this name, not GEMINI_API_KEY
```

### Harbor Results Recorded in the Evaluation Snapshot (Docker 29.8.1 + Harbor 0.26.0)

These are recorded results from the evaluation snapshot described below, not a fresh run of the current workspace. The live run store and rebuilt `data/derived/` leaderboard are not included in this clone.

| Run | Task | Actions | Levels | Reward |
|---|---|---:|---:|---:|
| **Reference (`oracle`)** | eval-v2 game 1 (`s910000`) | 187 | 8 / 8 | **1.000** |
| **Stop-early (L1)** | eval-v2 game 1 | 31 | 1 / 8 | **0.125** |
| **Do-nothing (`nop`)** | eval-v2 game 1 | 0 | 0 / 8 | **0.000** |
| **Reference (`oracle`)** | eval-v1 game 1 (`s900000`) | 86 | 6 / 6 | **1.000** |
| **OpenCode + Gemini 4 Carbon (`k=3`, 60-min cap)** | eval-v2 game 1 | 212 / 225 / 200 | 7/8 each | **0.762 mean** (`0.777`, `0.767`, `0.743`) |
| **OpenCode + Gemini 3.8 Flash (`k=3`, 60-min cap)** | eval-v2 game 1 | 250 / 191 / 84 | 6/8, 2/8, 2/8 | **0.322 mean** (two attempts quit early) |
| **OpenCode + Gemini 4 Argon (`k=3`, 60-min cap)** | eval-v2 game 1 | 60 / 63 / 63 | 2/8 each | 0.247 mean: OpenCode crashed on a Gemini 4 API error (agent-harness bug, see run logs) |
| **OpenCode + Nemotron (`k=3`, 30-min cap)** | dev game `s1000` | 155 / 135 / 227 | 1/6 each | **0.067 mean** (`0.020`, `0.094`, `0.087`) |

**What to expect from the agent runs on this game.** eval-v2 game 1 (`s910000`, 8 levels, shortest solution 187
moves) is the default task. Frontier models on it through our own multi-turn harness `h2`
(one continuous conversation, reasoning kept between turns, tool calls: the closest of our harnesses to OpenCode),
finished runs only, one attempt each:

| Model (h2, `arena/agent_h2.py`) | Levels solved | Moves | Wall time | Ended by |
|---|---:|---:|---:|---|
| Reference (`oracle`) | 8 / 8 | 187 | - | win |
| Gemini 4 Carbon (medium) | 6 / 8 | 209 | 84 min | cost cap |
| Gemini 3.8 Flash (high) | 3 / 8 | 289 | 50 min | cost cap |
| Gemini 3.1 Pro (medium) | 1 / 8 | 365 | 88 min | cost cap |
| DeepSeek 4.1 Flash (high) | 1 / 8 | 400 | 92 min | move budget |

No model has won this game. Gemini 4 Argon (2/8 after 67 moves) and Kimi K3.1 (1/8 after 146 moves) runs ended on
provider stalls and are not counted. Because these runs take up to ~90 min, every Harbor task gives the agent
**2 h** (`[agent] timeout_sec = 7200`), and `make judge` runs the K agent attempts in parallel (`N=1` for one at a time). The committed OpenCode runs above ([harbor/run-logs/](harbor/run-logs/README.md)) used the earlier 60-min cap: Gemini 4 Carbon reached 7/8 in all three and was still playing when the cap hit.

Full run logs (every attempt's reward, OpenCode event stream and trajectory): [harbor/run-logs/README.md](harbor/run-logs/README.md). Same folder: 15-min partial runs of Kimi K3.1, DeepSeek 4.1 Flash, Claude Haiku 5.5, DeepSeek V3.2, Nemotron and GLM 5.3 through Harbor + OpenCode (proof that each plays and is graded; capped, so not results). Every model in [arena/HARBOR.md](arena/HARBOR.md) ("Other models through OpenCode") plays through Harbor + OpenCode (smoke runs: Claude Haiku 5.5, Kimi K3.1, Gemini 4 Argon / Carbon, Gemini 3.8 Flash, Nemotron, DeepSeek V3.2, GLM 5.3). Reward-exploit red team (10 attacks from the agent's seat, all 0.0 or blocked): [docs/JUDGING.md](docs/JUDGING.md).

> *Note:* `python -m server mcp` is retained strictly for interactive local dev/demo inspection; official evaluation runs exclusively through `arena harbor-export` + `harbor run` ([arena/HARBOR.md](arena/HARBOR.md), [docs/JUDGING.md](docs/JUDGING.md)).

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

1. **Zero Text Hints + Per-Game `skin_shuffle` (runtime engine `0.6.0`, [rules/CATALOG.md](rules/CATALOG.md)):**
   Agents observe only a `64×64` frame of palette indices `0..15` ([contracts/palette.json](contracts/palette.json)) and `available_actions` (`RESET`, `ACTION1..4`; `ACTION5` interact is listed only in games that use it, none in the frozen sets; phase walls advance with every counted action). Colors and non-directional glyphs permute per game seed.
   - **HUD (`rows 0–1`):** move-budget bar shrinking per step.
   - **HUD (`rows 3–4`):** level progress pips + held-key / health / gem / stamina state indicators.
   - **Playfield (`rows 6–63`):** 15 Tier 1–2 rules, 3 opt-in Tier 3 rules (`conveyors`, `enemies`, `gravity`), and 3 additional difficulty-4 rules (`no_reverse`, `checkpoints`, `pits`). The three base mechanics are walls, goal, and move budget. See the catalog for difficulty and collection coverage.
2. **Four Generation-Time Fairness Proofs:**
   Every level passes exact BFS shortest-path verification (`optimal_moves`, `optimal_path`), rule-necessity ablation (removing any active rule alters optimal path or solvability), bounded budget slack (`ceil(optimal_moves × slack)`), and `< 2%` random-walk win rejection. Held-out `eval-v1` adds **unseen rule pairs** and **held-out visual skins** (`engine/src/engine/splits.py`).
3. **Action-Efficiency Reward Integrity ([analysis/METRICS.md](analysis/METRICS.md)):**
   $$\text{level\_score}(L) = \min\!\left(1.0,\; \frac{\text{optimal\_moves}(L)}{\text{actions\_used}(L)}\right) \text{ if solved else } 0.0$$
   - Do-nothing scores **`0.000`**; stopping early earns only the levels solved (Harbor oracle stopped after level 1: `1/8 = 0.125` on eval-v2), and the arena `stop_early` baseline (stops before finishing level 1) scores `0.000`. The denominator always spans `1..levels_total`.
   - `actions_used(L)` includes all actions taken before `RESET` plus `RESET` itself — reset farming strictly lowers efficiency.
   - `Truth` (`optimal_moves`, `events`, `active_rules`, `new_rule`) never enters LLM prompts or Harbor MCP responses.

---

## The Gap: Frozen `eval-v2` (Difficulty 4, `h1` / `h2` Harnesses)

Snapshot built on 2026-11-14 from the shared server's `1,006` runs (`python -m analysis sync && python -m analysis build`; practice, smoke and aborted runs filtered). The raw run data is not in the repo; `python -m analysis sync` downloads it from the live server. Score = mean over levels of `min(1, optimal / actions)` for solved levels, 0 otherwise; humans play each game once (first attempt).

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

*At the time of that snapshot,* Gemini 4 Carbon had one finished eval-v2 game at **0.789** (8/8); Claude Sonnet 5.5 had one at 0.044. The Gemini 4 sweep was then still in progress. These single-game observations are not cohort estimates.

**eval-v1 is the easy set:** on the one eval-v1 game they played, Gemini 4 Carbon / Argon / Hydrogen score 0.925 / 0.900 / 0.820, near the optimum and above humans. Use eval-v2 for the gap.

h1 = one fresh request per turn (notes + last 12 actions + frame); h2 = how labs benchmark (full history, reasoning kept, native tool calls, high effort). OpenCode in Harbor is a third harness (bash + code allowed); its numbers come from `make judge`.

*(Offline CI baseline in `data/fixtures/derived/leaderboard.json` is also committed and verified via `python -m analysis check-claims --derived data/fixtures/derived`.)*

---

## Tools and Infrastructure We Used

### Verda (DataCrunch)

- **Shared server and live site:** a Verda CPU VM (CPU.4V.16G, about $0.048/h) at `https://65.108.33.107.compute.verda.run` hosts the game server, every recorded run and the web app. Its URL is in [API_URL](API_URL).
- **GPU training and benchmarks:**
  - a 2x A100 80 GB box for the benchmark runs, SFT and the first GRPO runs ([posttrain/README.md](posttrain/README.md)),
  - a B200 for the `think-games` and `think-gridbranch` GRPO runs on Qwen3.5-9B and the held-out MATH test ([bench/heldout_math/README.md](bench/heldout_math/README.md)),
  - an A100 80 GB and an H100 80 GB for the rover transfer test and episodic RL on Qwen3.5-4B ([experiments/edge_rover/README.md](experiments/edge_rover/README.md)).
- **Model inference:**
  - Nemotron 3.5 Super VL from the hackathon deployment (see Nemotron below),
  - Kimi K3.1 Pro and DeepSeek 4.1 Flash through Verda's managed inference API (`https://inference.verda.com/v1`). Kimi ran in the overnight `dev` sweep (52% of levels solved) and in the `h2` runs until the account was suspended. Both have short Harbor + OpenCode runs in [harbor/run-logs/README.md](harbor/run-logs/README.md).

  Endpoints and keys: [arena/models.yaml](arena/models.yaml), [docs/KEYS.md](docs/KEYS.md).

### NVIDIA Nemotron

- Nemotron 3.5 Super VL (120B MoE, 12B active, NVFP4) on the organisers' Verda endpoint, with text and image input. Registered as `nemotron-3-5-super-vl` in [arena/models.yaml](arena/models.yaml).
- **Harbor judge path:** OpenCode + Nemotron played the dev game `s1000` through Harbor with the organisers' OpenCode config ([arena/opencode-nemotron.json](arena/opencode-nemotron.json)). It scored 0.067 on average over three attempts ([docs/JUDGING.md](docs/JUDGING.md)).
- **Arena runs:** the overnight `dev` sweep (12% of levels) and a 3-game `eval-v1` subset ([arena/sweeps/main-subset-nemotron.yaml](arena/sweeps/main-subset-nemotron.yaml)). The endpoint takes about 30 s per action, so a full sweep was not practical.

### Gemma

- Gemma 4 E4B, served on our own Modal endpoint (see Modal below), finished 21 runs of the `eval-v1` sweep ([arena/sweeps/main-gemma.yaml](arena/sweeps/main-gemma.yaml)) and solved 4 of 126 levels (3%).
- Gemma 4 31B through the Gemini API was registered but dropped. The key allows 16k input tokens per minute, and one `h2` turn sends 20k to 45k.

### Gemini API

- **Frontier reference models:** Gemini 4 Carbon, Argon and Hydrogen, Gemini 3.8 Flash and Gemini 3.1 Pro, in the `h1`, `h2` and `h2b` sweeps on `eval-v1` and `eval-v2` (the gap numbers above).
- **Harbor:** OpenCode + Gemini 4 Carbon averaged 0.762 over three attempts on the first `eval-v2` game ([harbor/run-logs/README.md](harbor/run-logs/README.md)).
- **Rover transfer test:** Gemini 4 Argon, Carbon and Flash are the frontier reference on the simulated rover ([experiments/edge_rover/README.md](experiments/edge_rover/README.md)).

### Modal

- **RL training:** GRPO runs `grpo-1` and `grpo-2` on Qwen3.5-9B, each on a Modal H100, using the same trainer as the Verda boxes ([posttrain/modal_grpo.py](posttrain/modal_grpo.py)). Checkpoints and the Hugging Face cache live in Modal volumes.
- **Model serving:** an SGLang endpoint serving Gemma 4 E4B (OpenAI-compatible, provider `modal` in [arena/src/arena/providers/openai_compat.py](arena/src/arena/providers/openai_compat.py)).

### Codex (development)

- Wrote the first version of the rover transfer experiment (`mission.py`, `run_eval.py`, the game bootcamp LoRA on Qwen2.5-1.5B), kept for the record in [experiments/edge_rover/README.md](experiments/edge_rover/README.md).
- Worked on the story deck on the `codex/*` branches: slide copy, model colours, styling, the rover cover slide, video alignment and the PDF export ([docs/story-deck/](docs/story-deck/)).

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
| `docs/` | Submission sheet, judging path and results, API keys, business case, story deck (HTML + PDF) | [docs/SUBMISSION.md](docs/SUBMISSION.md), [docs/JUDGING.md](docs/JUDGING.md), [docs/BUSINESS.md](docs/BUSINESS.md), [docs/story-deck/index.html](docs/story-deck/index.html), [docs/story-deck/Game-Factory-Pitch-Deck.pdf](docs/story-deck/Game-Factory-Pitch-Deck.pdf) |
| `rules/proposals/` | Tier-2/3 specs + automated `eval-v2` failure-driven proposals | [rules/proposals/auto-04-eval-v2-tier3-drift-and-timing.md](rules/proposals/auto-04-eval-v2-tier3-drift-and-timing.md) |
