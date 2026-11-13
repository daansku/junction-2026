# PLAN.md — Junction 2026 build plan

**Clock:** revised Sat 14.11 01:25 (Helsinki). **Final submission: Sun 15.11 10:00.** We submit at **09:30**. ~32 working hours.

**What we are building, in one sentence:** a factory that produces unlimited, seed-reproducible, verified-solvable ARC-AGI-3-style games, plus the arena that shows where frontier models still lose to humans (and to a small fine-tuned model) on games nobody has seen before.

Every agent reads sections 1–5 in full, then its own section in 6. Humans read 1, 2 and 7.

---

## 1. Scope

### Must ship (the demo dies without these)
1. **Game factory** — procedural, seeded, multi-level grid games; one new rule introduced per level; rule combinations never repeat inside a game; every level proven solvable; move budget derived from the optimal solution.
2. **Pixels-only agent interface** — MCP server + REST. The agent receives a 64×64 frame and nothing else. No win/lose flag, no score, no rule names.
3. **Human play UI** — same frames, arrow keys.
4. **Replay viewer** — watch any run step by step with the model's reasoning next to the frame.
5. **Puzzle gallery** — browse the collection, rules per level, optimal path.
6. **Model leaderboard** — several providers, performance, tokens, cost, cost-vs-performance chart, model links/specs.
7. **Post-game analysis** — where models learn a rule fast, where they never do, compared with human and optimal play.
8. **Pitch deck + demo.**

### Stretch (cut from the bottom up when behind)
1. Analysis → new rules → second eval collection (the "factory improves itself" loop)
2. Fine-tuned small model beating un-tuned frontier models on held-out games
3. Effort-level comparison
4. Live spectating wall (several models playing at once)
5. ARC-AGI-3-compatible REST shim, so existing community agents can be pointed at our games
6. 3D map rotation

### Assumptions made (humans: correct these in `coordination/DECISIONS.md`)
- Each agent runs on its own machine with its own clone of the repo. The machines share exactly two things: the GitHub remote and one shared server URL (§3.4).
- Python 3.11+ backend, React + TypeScript + Vite frontend.
- We write our own small engine, wire-compatible with ARC-AGI-3 (64×64 frame, 16 colours, `RESET` + `ACTION1..7`). We do not depend on the official `arcengine` package.
- No API keys are in hand yet. Agents build against mocks until keys land in `.env`.
- Aiven is a database provider, not GPU compute. Fine-tuning goes to Modal. Aiven Postgres is optional run storage only if a human decides it matters for a challenge.

---

## 2. Gates

Each gate is a hard integration point. At a gate every agent: rebases on `main`, runs `scripts/smoke.sh`, updates its status file. Gates G1 and G5-prep fall in a window where no human input is needed. Agents are on different machines, so "rebase on `main`" is the only way anyone sees anyone else's work.

| Gate | Time | What must work end to end |
|---|---|---|
| **G0** | Sat 02:15 | Contracts + fixtures committed. Stub engine (walls + goal + budget) importable. Web shell with all routes. Every agent unblocked. |
| **G0+** | Sat 03:00 | Shared server reachable from all five machines; URL committed to `coordination/API_URL`. |
| **G1** | Sat 06:00 | **Vertical slice:** a generated 6-level game is playable in the browser, playable by one real model through the harness, the run is recorded, and the replay shows up in the viewer. |
| **G2** | Sat 13:00 | **Breadth:** ≥ 12 rules, `eval-v1` collection frozen, ≥ 6 models from ≥ 3 providers run on a pilot subset, gallery + leaderboard on real data, human baseline traces exist, draft submission opened. |
| **G3** | Sat 20:00 | Main sweep finished. Analysis v1 with 3 headline findings. Fine-tune result or a decision to cut it. `eval-v2` (rules born from analysis) generated. |
| **G4** | Sun 00:00 | **Feature freeze.** Public demo URL live in read-only mode. Deck v1. Demo video recorded. Only bug fixes and overnight eval runs after this. |
| **G5** | Sun 08:30 | Final numbers locked (07:00), deck matches data, submission text final. **Submit 09:30.** |

---

## 3. Working rules for all agents

### 3.1 Ownership — the rule that makes parallel work possible
You write only inside the paths you own (table in §3.2). Need a change elsewhere? Create `coordination/requests/<from>-to-<to>-<slug>.md` (what, why, by when) and carry on with a mock. The owner picks requests up at the top of each hour.

### 3.2 Folder structure and owners

```
.
├── PLAN.md                      humans only
├── README.md                    A5
├── Makefile, scripts/           A2   (setup, dev, test, smoke, demo)
├── .env.example                 A3   (.env is never committed)
├── contracts/                   A2   single writer; additive-only after G0
│   ├── palette.json             16 colours, index 0–15
│   ├── engine_api.py            Protocol stubs (§4.3)
│   ├── openapi.yaml             REST (§4.4)
│   ├── trace.schema.json        run traces (§4.5)
│   └── derived.schema.json      leaderboard + analysis outputs (§4.6)
├── engine/                      A1
│   ├── src/engine/core/         state, actions, game loop, events, seeded rng
│   ├── src/engine/components/   ONE FILE PER COMPONENT (keys_doors.py, ice.py, …)
│   ├── src/engine/generator/    layout, placement, curriculum (rule intro + shuffle)
│   ├── src/engine/solver/       bfs, budget, rule-necessity, random-walk check
│   ├── src/engine/render/       grid → 64×64 frame, HUD, PNG
│   ├── src/engine/cli.py        gen / play / render / verify
│   └── tests/
├── server/                      A2
│   ├── src/server/              app, sessions, recorder, routes/, live (WS),
│   │                            mcp_server, arc_compat (stretch)
│   └── tests/
├── arena/                       A3
│   ├── models.yaml              model registry (§4.7)
│   ├── src/arena/               providers/, agent_loop, prompts/, runner, cost, budget
│   ├── sweeps/                  one yaml per eval sweep
│   ├── finetune/                make_dataset, modal_train, modal_serve
│   └── tests/
├── analysis/                    A5
│   ├── METRICS.md               exact metric definitions
│   └── src/analysis/            aggregate, rule_discovery, compare, insights
├── web/                         A4, except the two folders marked A5
│   ├── DESIGN.md                A4   design direction; A5 follows it
│   ├── package.json             A4   (dependency requests go through A4)
│   └── src/
│       ├── app/                 A4   router, layout
│       ├── design/              A4   tokens, primitives
│       ├── lib/                 A4   api client, FrameCanvas, mock mode
│       └── features/
│           ├── play/            A4
│           ├── gallery/         A4
│           ├── replay/          A4   replay + live spectate
│           ├── leaderboard/     A5
│           └── insights/        A5
├── rules/
│   ├── proposals/               humans + A5 add files; A1 implements
│   └── CATALOG.md               A1   every rule: status, tier, visuals, teaching level
├── data/
│   ├── fixtures/                A2 (+ fixtures/derived/ by A5)  committed sample data
│   ├── collections/             A1   frozen puzzle collections (committed)
│   ├── runs/                    gitignored — traces, written only by the server
│   ├── derived/                 gitignored — written only by analysis
│   └── published/               A2   committed snapshot used by the public demo
├── docs/                        A5   research/, PITCH.md, DEMO_SCRIPT.md, SUBMISSION.md, deck/
└── coordination/
    ├── status/A1.md … A5.md     each agent writes only its own
    ├── requests/                new files only, never edit someone else's
    └── DECISIONS.md             humans only
```

No shared lockfile and no root `pyproject.toml`: each Python package has its own `pyproject.toml` and adds its own dependencies. One venv per clone, built by `make setup` (`pip install -e ./engine -e ./server -e ./arena -e ./analysis`).

### 3.3 Git
- One clone and one branch per agent machine: `agent/a1` … `agent/a5`.
- Git is the only channel between agents. `git fetch && git rebase origin/main` at least every 30 minutes and before starting each new task; push after each finished task.
- Commit small, prefix the message with your id: `[A3] add gemini provider`.
- Ship to main often: `git fetch origin && git rebase origin/main && git push origin HEAD:main`. Rejected push → fetch, rebase, push again. Directories are disjoint, so rebases are conflict-free. If you hit a conflict you edited something you do not own — stop and revert that edit.
- Never force-push. Never commit `.env`, `data/runs/`, `node_modules/`.

### 3.4 Shared runtime (agents are on different machines)
- **One shared server holds every trace.** It runs on the host named in `DECISIONS.md` (default: A2's machine behind a tunnel that works on the venue network; move to a cloud VM as soon as a human provides one). A2 commits its public address to `coordination/API_URL` **by 03:00** and again whenever it changes. Every run that counts (model sweeps, human playtests, baselines) goes through that URL, so all traces land in one `DATA_DIR` on that host.
- The shared host also serves the built web app from `main`, so humans playtest and review at one address.
- **Local dev is local.** Each machine runs its own server and web on localhost against its own throwaway `DATA_DIR` (`~/junction-data`). Local traces are never used for results.
- A2 keeps the shared server on current `main`: pulls and restarts at every gate and on request, never in the middle of a sweep (check A3's status file first). Tars `DATA_DIR` hourly to a second location; lost traces are lost money.
- **Reading traces from another machine** goes through the API only. `GET /runs/export?since=` returns finished runs as a tar; `python -m analysis sync` mirrors them into a local cache. The shared host runs `analysis build` on `POST /admin/rebuild` and serves the output at `/derived/`, so web pages never need local traces.
- **Secrets:** model keys and the Modal token live only in `.env` on A3's machine. The shared host needs none. `/admin/*` requires `ADMIN_TOKEN`. Humans pass keys and the token over a private channel, never through git.
- The host machine must not sleep: on power, sleep disabled, one human responsible for it.

### 3.5 Working unattended
- Do not wait for a human or another agent. Blocked for more than 10 minutes → write the blocker in your status file, switch to the next task in your list, keep going on a mock.
- Update `coordination/status/A<n>.md` at every gate and whenever blocked: **Done / Doing / Blocked / Need from humans**. Humans read these five files, nothing else.
- A task is done when it runs: tests pass, and you exercised it yourself (played the level, opened the page, read the trace).
- **Spending:** before any model sweep, the runner prints a cost estimate. Above the cap in `DECISIONS.md` (default **$5 per sweep** until a human raises it) you stop and ask.
- **Model IDs, prices, SDK details:** look them up in the provider's current docs. Do not write them from memory.
- **Any UI or deck work:** first search for and load a UI/frontend design skill, and read `web/DESIGN.md`. No purple gradients, no emoji as icons, no glass cards, no "hero + three feature cards". The pixel grid and its 16-colour palette are the visual identity; the dashboards should read like a dense benchmark or sports-stats site.

---

## 4. Contracts

These are frozen at G0. PLAN.md is the source of truth until A2 has written `contracts/` (by 01:55); after that `contracts/` wins. Changes after G0 are additive only and go through a request to A2.

### 4.1 Frame
- Always **64×64**, each cell an int **0–15**, palette in `contracts/palette.json`.
- Wire format: 64 strings of 64 hex characters (`"0003aa…"`), row 0 at the top.
- **Everything a player may know is drawn in the frame**: remaining-moves bar, health, stamina, inventory, win screen, game-over screen. The HUD lives in the top rows; the play area is the logical grid scaled by an integer cell size.
- No text, no legends, no numbers. Rules are discovered by acting, as in ARC-AGI-3.

### 4.2 Actions (ARC-AGI-3 compatible)
| Action | Meaning | Human key |
|---|---|---|
| `RESET` | restart the current level (counted) | R |
| `ACTION1` | up | ↑ / W |
| `ACTION2` | down | ↓ / S |
| `ACTION3` | left | ← / A |
| `ACTION4` | right | → / D |
| `ACTION5` | interact (only in games that use it) | Space |
| `ACTION6` | click `x,y` in 0–63 (reserved, unused in v1) | mouse |
| `ACTION7` | undo (disabled in v1) | Z |

After game over, every action except `RESET` leaves the frame unchanged.

### 4.3 Engine API (A1 provides; A2, A3, A5 consume)
```python
spec = GameSpec(family="gridworld", seed=1234, n_levels=6, difficulty=2,
                rules=None, skin_shuffle=True)      # rules=None → curriculum picks
game = make_game(spec)            # or load_game(collection, game_id) for frozen games
frame = game.reset()              # -> Frame (64 hex rows)
frame = game.step(Action.ACTION1) # -> Frame
game.truth()      # -> Truth, hidden from agents, see below
game.describe()   # -> metadata: rules per level, budgets, optimal path per level, engine_version
game.clone(); game.state_hash()   # for the solver
```
```json
// Truth
{"state":"NOT_FINISHED|WIN|GAME_OVER","level":2,"levels_total":6,
 "moves_used":17,"move_budget":40,"resets":1,
 "active_rules":["keys_doors","ice"],"new_rule":"ice",
 "events":["picked_key","slid:4"],"optimal_moves":22}
```
- `game_id` is a stable string: `gridworld-s1234-d2-l6-<hash8>`.
- **Determinism:** same spec + same engine version → byte-identical frames. Seeded `random.Random` derived with `hashlib` from (seed, level, attempt). No global `random`, no builtin `hash()`.
- **Collections are frozen snapshots:** a collection file stores spec + `engine_version` + the materialised levels. Evals always load from the snapshot, so adding rules later never changes an existing eval game.

### 4.4 REST (A2 provides; A3 and web consume) — base `/api`
| Method & path | Body → response | Notes |
|---|---|---|
| `GET /games?collection=` | → list of game metadata + thumbnail URL | gallery |
| `GET /games/{game_id}` | → `describe()` output | contains truth; UI only |
| `POST /sessions` | `{game_id, player:{kind:"human"\|"model"\|"baseline", name, model_id?, effort?}, run_key?}` → `{session_id, run_id, frame, available_actions}` | |
| `POST /sessions/{id}/act` | `{action, x?, y?, reasoning?, hypothesis?, belief?, usage?}` → `{frame, available_actions}` | **pixels only** |
| `GET /sessions/{id}/truth` | → Truth | harness and human debug overlay; never shown to a model |
| `POST /sessions/{id}/end` | `{reason}` | closes the run |
| `GET /runs?game_id=&model_id=&kind=` | → run metas | |
| `GET /runs/{run_id}` · `/runs/{run_id}/steps` | → meta · steps | replay |
| `GET /runs/export?since=<iso time>` | → tar of run folders finished since then | how other machines read traces |
| `POST /admin/rebuild` | → runs `analysis build` on the shared host | needs `ADMIN_TOKEN` |
| `GET /derived/{name}.json` | → file from `data/derived/` (or `published/`) | leaderboard, insights |
| `WS /live` | stream of `{run_id, step}` | spectate |

**MCP server** (same session core): tools `list_games()`, `start_game(game_id)`, `act(action, x?, y?, note?)`, `reset()`. Each returns the frame as a PNG image **and** as a text grid. Nothing else.

### 4.5 Trace (written only by the server; read by web and analysis)
`$DATA_DIR/runs/<run_id>/meta.json`
```json
{"run_id":"…","run_key":"…","game_id":"…","collection":"eval-v1","split":"test",
 "player":{"kind":"model","name":"…","model_id":"…","provider":"…","effort":"medium"},
 "harness_version":"h1","started_at":"…","ended_at":"…",
 "outcome":"WIN|GAME_OVER|BUDGET|ABORTED","levels_completed":4,"levels_total":6,
 "actions":212,"resets":3,"tokens_in":0,"tokens_out":0,"cost_usd":0.0,"wall_s":0}
```
`steps.jsonl`, one line per action:
```json
{"i":17,"t_ms":41250,"action":"ACTION3","frame":["…64 hex rows…"],
 "truth":{…},"reasoning":"…","hypothesis":"blue tile opens the gate",
 "belief":"playing|won|lost","usage":{"in":0,"out":0,"cost_usd":0.0},"latency_ms":900}
```
`run_key = sha1(collection, game_id, model_id, effort, harness_version, attempt)` — the runner skips keys that already have a finished run, so sweeps are resumable.

### 4.6 Derived data (written only by `analysis`; read by web)
- `leaderboard.json` — one row per (model, effort, collection): games, level solve rate, game win rate, **score**, median actions, tokens, cost per game, cost per solved level, latency, plus the model card from `models.yaml`. Baselines `random`, `optimal`, `human` are rows too.
- `rules.json` — rule × model matrix: solve rate on the level that introduces the rule, actions to first correct use, wasted actions.
- `insights.json` — headline findings, each with evidence and deep links to replays.
- **Score** (headline metric, in the spirit of ARC-AGI-3's action-efficiency scoring): mean over all levels of `min(1, optimal_moves / actions_used)` for solved levels and `0` for unsolved ones. Actions before a reset count.

### 4.7 Model registry — `arena/models.yaml`
```yaml
- id: <our stable id>
  display_name: …
  provider: anthropic | google | nvidia | featherless | verda | modal
  api_model: <exact id from provider docs>
  tier: frontier | open | finetuned
  input_modes: [image, text]
  efforts: [low, medium, high]      # omit if unsupported
  price_in: …    # USD per 1M tokens, null if unknown
  price_out: …
  params: …      # e.g. "8B"
  link: <model card URL>
```

---

## 5. Game design rules (binding for A1, context for everyone)

- **Curriculum:** a game has 6 levels by default. Level 1 is movement + goal. Each later level introduces exactly one new rule in a small "teaching" layout where its effect cannot be missed, then later levels recombine. No two levels in a game use the same rule set. Which rules, in which order, is decided by the seed.
- **Solvable:** BFS over the full game state proves it. Unsolvable candidates are discarded and regenerated with the next sub-seed.
- **The new rule must matter:** solve the level again with the new component neutralised; if the optimal length is unchanged, reject the level.
- **Budget:** `move_budget = ceil(optimal × slack)`, slack 1.5–3.0 by difficulty, plus an exploration allowance on levels that introduce a rule. Budget exhausted or health zero → game over for that level → `RESET` restarts it.
- **Not brute-forceable:** a random-walk agent must win a level under budget in < 2% of 200 tries, otherwise reject.
- **Human-doable:** humans playtest; any level two humans fail to solve in 3 attempts gets flagged in `rules/proposals/feedback-*.md` and A1 retunes.
- **Skin shuffle:** per game, the colours/shapes of components are permuted by the seed, so no player — human, frontier model or fine-tuned model — can memorise "red means key".
- **Rule backlog** (A1 implements top-down; one file each in `engine/components/`):
  - *Tier 0 (G0):* walls, goal, move-budget bar
  - *Tier 1 (G1):* keys + doors · pressure plates + gates · teleporter pairs · hazards + health bar · pushable blocks · one-way tiles · ice (slide until blocked)
  - *Tier 2 (G2):* shadow that follows one step behind · mirror twin copying moves · 2D rotation trigger · control remap trigger · stamina + refills · shields · walls that toggle every k moves · collect-all-before-goal · teleporter variants (one-way, colour-linked)
  - *Tier 3 (stretch):* 3D rotation (two-layer map flip) · conveyor belts · patrolling enemies · gravity switch
  - plus everything in `rules/proposals/` from humans and from A5's analysis

---

## 6. Agent plans

Times are Helsinki. Task ids are for status files. Each agent has work in every window; nobody idles waiting for another.

### Parallel timeline at a glance

| Window | A1 FORGE | A2 GATEWAY | A3 ARENA | A4 STUDIO | A5 LENS |
|---|---|---|---|---|---|
| **P0** 01:30–02:15 | engine core, renderer, stub game | contracts, fixtures, server skeleton on fake engine | providers, registry, random agent | design skill, DESIGN.md, web shell + mock mode | research digest, metrics spec, derived fixtures |
| **P1** 02:15–06:00 | solver, generator, Tier 1, curriculum, `dev` collection | **shared URL by 03:00**, real engine wiring, recorder, runs API, MCP, live WS | agent loop, cost accounting, runner, first real traces | Play page, Replay page | aggregation, Leaderboard page |
| **P2** 06:00–13:00 | Tier 2, skin shuffle, human rules, freeze `eval-v1`, `train-v1` | derived serving, hardening, Docker, published mode | full registry, efforts, pilot sweep, freeze harness, fine-tune dataset | Gallery, game detail, live spectate, compare view | rule-discovery analysis, Insights page |
| **P3** 13:00–20:00 | rules from analysis, `eval-v2`, fuzzing, Tier 3 | deploy, load test, backups, ARC shim | main sweep, fine-tune + serve + eval, effort ablation | polish, overview page, projector QA | findings, auto rule proposals, pitch, deck, submission text |
| **P4** 20:00–00:00 | bug fixes, contact sheets for deck | `make demo`, offline fallback, freeze | `eval-v2` sweep, reruns | published build, screenshots, QA | deck v1, demo script, README |
| **P5** 00:00–08:30 | on call for bugs | on call, keep stack alive | overnight runs, lock numbers 07:00 | on call for bugs | final numbers into deck, claim check |

---

### A1 — FORGE (engine and factory) · owns `engine/`, `data/collections/`, `rules/CATALOG.md`
You are the critical path. Ship the stub first, then deepen.

**P0**
- A1-01 Core: state, `Action`, `Game` with `reset/step/truth/describe/clone/state_hash`, seeded RNG.
- A1-02 Renderer: logical grid → 64×64 frame with HUD; PNG export.
- A1-03 **Stub game pushed by 02:00**: walls + goal + budget, 3 levels. This unblocks A2.

**P1**
- A1-04 Component plugin interface + registry (place, on_enter, on_step, render, solver hooks). One file per component from here on.
- A1-05 Solver: BFS with state cap, budget calculation, rule-necessity check, random-walk check.
- A1-06 Generator: layouts (rooms, maze, open), constrained placement, validate-and-retry loop.
- A1-07 Tier 1 components, each with a teaching layout and a test.
- A1-08 Curriculum: rule introduction order, shuffle, unique combinations.
- A1-09 CLI: `gen`, `play` (terminal), `render` (PNG contact sheet), `verify <collection>`.
- A1-10 `data/collections/dev.json` (10 games). Determinism test: generate twice, hashes equal.

**P2**
- A1-11 Tier 2 components.
- A1-12 Skin shuffle.
- A1-13 Implement human proposals from `rules/proposals/`.
- A1-14 Difficulty calibration from playtest feedback. **Freeze `eval-v1.json` at 11:00** (30 games, 3 difficulty bands). Generate `train-v1.json` (≥ 2,000 games, seeds disjoint from eval, with a documented list of rule combinations and skins held out for eval only).

**P3**
- A1-15 Implement A5's `rules/proposals/auto-*.md`. Generate `eval-v2.json` targeting what models failed at.
- A1-16 Fuzz: 1,000 seeds → all solvable, no crash, deterministic.
- A1-17 Tier 3 if time.

**P4–P5** Engine frozen at 22:00 except bug fixes. Render contact sheets and level GIFs for A5's deck.

**Done means:** `python -m engine verify data/collections/eval-v1.json` passes; every rule in `CATALOG.md` has a test and a teaching level.

---

### A2 — GATEWAY (server, MCP, traces, deploy) · owns `server/`, `contracts/`, `data/fixtures/`, `data/published/`, `scripts/`, `Makefile`
You are the hub. Everyone else talks through you, so contracts and fixtures come first.

**P0**
- A2-01 **By 01:55:** write `contracts/` from §4 and `data/fixtures/`: sample frames, a catalogue of 3 games, one complete 30-step run (meta + steps) with reasoning text. Web and analysis build on these.
- A2-02 FastAPI skeleton, session core on a fake engine, `make setup / dev / test`, `scripts/smoke.sh`.

**P1**
- A2-08 **First task of P1, done by 03:00:** shared server up on the host from `DECISIONS.md`, serving API and built web, opened successfully from a second machine, URL committed to `coordination/API_URL`. Use the stub engine if the real one is not ready.
- A2-03 Wire the real engine as soon as A1-03 lands.
- A2-04 Recorder: `meta.json` + append-only `steps.jsonl`, safe under concurrent sessions.
- A2-05 Catalogue and runs endpoints including `/runs/export`; thumbnails through the engine renderer.
- A2-06 MCP server (stdio and HTTP): image + text grid, pixels only. Test it by letting an MCP client play a level.
- A2-07 `WS /live`.

**P2**
- A2-09 Serve `data/derived/`; trigger `analysis` rebuild on demand (`POST /admin/rebuild`).
- A2-10 Hardening: 50 parallel sessions, idempotent `run_key`, crash-safe traces, hourly backup of `DATA_DIR`.
- A2-11 Dockerfile; **published mode**: read-only, serves `data/published/`, human play works with no keys, and no visitor action can trigger a paid model call.

**P3**
- A2-12 If the shared server is still on a laptop tunnel, move it to the final host (decision due 13:00): stop sweeps with A3, copy `DATA_DIR`, start, commit the new `coordination/API_URL`. Verify from a phone.
- A2-13 Stretch: ARC-AGI-3-shaped REST shim (`/api/cmd/RESET`, `/api/cmd/ACTION1` …) so community agents can run on our games.

**P4–P5** `make demo` starts everything with one command; offline fallback from `data/published/`; snapshot final data at 07:00 Sun.

**Done means:** `scripts/smoke.sh` creates a session, plays to a win with the optimal path, and finds the run through `/runs`.

---

### A3 — ARENA (models, evaluation, fine-tuning) · owns `arena/`, `.env.example`
One harness, identical for every model. Fairness is what makes the leaderboard credible.

**P0** (needs no game yet)
- A3-01 `.env.example` listing every key; provider adapters: Anthropic, Google Gemini, and one OpenAI-compatible adapter covering featherless, NVIDIA, Verda and Modal-hosted models. Check current model ids and prices in each provider's docs.
- A3-02 `models.yaml` skeleton. Baseline players: `random`, and `optimal` (replays the engine's optimal path through the API).

**P1**
- A3-03 Agent loop v1: generic system prompt (you see frames, you can act, work out the goal and rules); observation as image and/or text grid per `input_modes`; rolling notes the model maintains; JSON output `{notes, hypothesis, belief, action}`. `hypothesis` and `belief` are sent to the server for analysis.
- A3-04 Token and cost accounting; per-game budgets for tokens, wall time and total actions → outcome `BUDGET`.
- A3-05 Runner: sweep yaml, async concurrency, per-provider rate limits, retries, resume by `run_key`, `--dry-run` cost estimate.
- A3-06 **First real traces by ~04:30:** smoke sweep through the shared `API_URL`, 2 cheap models × 3 `dev` games, plus `random` and `optimal` on all of `dev`. Sweeps always target the shared server; a local server is for debugging the harness only.

**P2**
- A3-07 Fill the registry: ≥ 8 models over ≥ 4 providers as keys arrive; effort levels where the API supports them.
- A3-08 Pilot sweep on 5 `eval-v1` games. Fix harness problems, then **freeze the harness as `h1` at 12:00**. Later harness changes get a new version and never mix in one leaderboard.
- A3-09 Fine-tune dataset from `train-v1`: optimal trajectories plus recover-from-mistake trajectories. Any agent-side perception (e.g. downsampling the frame to logical cells) is allowed but must be applied to every model and stated on the dashboard.

**P3**
- A3-10 **Main sweep** on `eval-v1` after the human approves the estimate (13:00). Expensive models get a subset; say so in the data.
- A3-11 Fine-tune a small open model on Modal (go/no-go 14:00), serve it behind an OpenAI-compatible endpoint, register it as `tier: finetuned`, evaluate on `eval-v1` only. **No result on the board by 22:00 → cut from the pitch.**
- A3-12 Effort ablation on 2 models.

**P4–P5** Sweep `eval-v2`; rerun failed runs; numbers lock at 07:00 Sun.

**Done means:** `python -m arena run sweeps/main.yaml --dry-run` prints runs and cost; a real run produces traces that validate against `trace.schema.json`.

---

### A4 — STUDIO (web: play, gallery, replay) · owns `web/` except `features/leaderboard` and `features/insights`
**P0**
- A4-01 Search for and load a UI design skill. Write `web/DESIGN.md` in 20 minutes: direction, type, colour tokens, spacing, table and chart conventions, do/don't list. A human looks at it at 02:30.
- A4-02 **Shell pushed by 02:15:** Vite + React + TS, router with routes `/play`, `/gallery`, `/replay/:run`, `/leaderboard`, `/insights`, stub folders for A5, API client where `VITE_API` is `mock` (reads `data/fixtures/`), localhost, or the shared URL, `FrameCanvas` (crisp 64×64 pixel rendering from the palette), one charting library installed that covers scatter, line and heatmap.

**P1**
- A4-03 **Play:** arrow keys / WASD / R, player name, game picker; the human sees exactly the model's frame. Optional debug overlay toggle for truth.
- A4-04 **Replay:** scrubber, play/pause/speed, step list, reasoning + hypothesis pane beside the frame, timeline with level changes, resets and events.

**P2**
- A4-05 **Gallery:** thumbnail grid, filters by rule and difficulty; game detail with levels, rule per level, optimal-path overlay, budget, per-model results, links to play and replays.
- A4-06 **Live spectate:** watch a run in progress; wall view with several models at once.
- A4-07 **Compare:** human vs model vs optimal on the same level, side by side.

**P3** Overview page for peer reviewers (what this is, play now, see results); loading/empty/error states; keyboard-first; projector check at 1080p.

**P4–P5** Published-mode build, screenshot set for the deck, QA with humans, bug fixes only after freeze.

**Done means:** a person who has never seen the project can open the site, play a game and watch a model replay without being told how.

---

### A5 — LENS (leaderboard, analysis, story) · owns `analysis/`, `docs/`, `README.md`, `web/src/features/leaderboard`, `web/src/features/insights`, `data/fixtures/derived/`
**P0**
- A5-01 Research digest, 45 minutes max → `docs/research/DIGEST.md`: ARC Prize winning write-ups, ARC-AGI-3 preview agents, community leaderboard approaches. Output must be actionable: rule ideas as files in `rules/proposals/`, harness and fine-tuning ideas as a request to A3.
- A5-02 `analysis/METRICS.md` and `data/fixtures/derived/*.json` matching §4.6.

**P1**
- A5-03 `sync` (mirror traces from the shared server via `/runs/export`) and `aggregate` (traces → `leaderboard.json`). Works on the fixture run first, on real traces from 04:30.
- A5-04 **Leaderboard page** (follow `web/DESIGN.md`; load a data-viz skill if available): sortable table, cost-vs-score scatter with log cost axis, model cards with links and specs, effort comparison, baselines `random` / `human` / `optimal` shown as reference lines.

**P2**
- A5-05 Rule-discovery analysis per rule × model: solve rate on the introducing level, actions to first correct use, wasted actions, repeated no-effect actions (a sign of not learning), whether the stated `hypothesis` ever matches the rule, whether `belief` matched the real outcome (did it know it had won or lost). Same numbers for humans and optimal.
- A5-06 **Insights page:** rule × model heatmap, learning curve across levels, failure types, each finding linked to a replay.

**P3**
- A5-07 Three headline findings with evidence → `insights.json`. Write `rules/proposals/auto-*.md` for A1, each citing the failure it exploits.
- A5-08 Story: `docs/PITCH.md`, `docs/DEMO_SCRIPT.md`, `docs/SUBMISSION.md` (fields from the human's draft submission), deck in `docs/deck/`. Search for skills/prompts for human-sounding writing and for presentation design first.

**P4–P5** README; final numbers into the deck; **claim check** — every number in deck and submission traces to a file in `data/derived/`; Q&A prep sheet.

**Done means:** `python -m analysis build` regenerates every derived file from a synced trace folder, the same command works on the shared host, and both pages render the result.

---

## 7. Humans — what only you can do, and when

Every machine has a **keeper**: the person who restarts its agent if it stops and answers its status file. Further roles (one person can hold several): **Integrator** (main branch, shared server host) · **Keys & budget** · **Playtester / rule designer** · **Storyteller** (deck, pitch, submission).

| When | Task | Why an agent can't |
|---|---|---|
| **Sat 01:25–01:45** | One person: create the GitHub repo, run Appendix A, add this file, push, give everyone access. Everyone else: clone, then start your agent with Appendix B. | accounts, terminals |
| **01:45–02:30** | Send every key you already have to the keeper of A3's machine over a private channel, for its `.env`. Fill `coordination/DECISIONS.md`: project name, shared-server host, spend cap per sweep, total budget, challenge/track. | accounts, money |
| **02:30–02:45** | 5-minute look at `web/DESIGN.md` and `contracts/`. Say no now, not at noon. | taste, final say |
| **03:00** | Open the address in `coordination/API_URL` from a machine that is not the host. Put the host on power with sleep disabled. | physical machines, network |
| **any time before 09:00** | Write 5–10 rule ideas, one file each in `rules/proposals/` (what it looks like, what it does, why it is hard for a model). | the plan calls for human-made rules |
| **03:00–09:00** | *No human input needed.* Everything in P1 is pre-approved if keys and the spend cap are in place. | |
| **09:00–09:30** | G1 review: read the five status files, play 3 games, watch one replay, answer blockers. | |
| **09:30–12:00** | Playtest `dev` on the shared URL under your own names (these become the human baseline; local plays are not recorded centrally). Write feedback files. Collect remaining keys and credits from partner booths. | only humans know if it is fun and fair |
| **11:00** | Approve freezing `eval-v1`. | changes after this invalidate results |
| **12:00** | Submissions open: create the draft, copy every required field and rule (video? repo? live URL? pitch length?) into `docs/SUBMISSION.md`. Confirm Friday's pre-submission went through. | platform login |
| **13:00** | G2 review. Approve A3's main-sweep cost estimate. Choose the deploy host. | money |
| **13:30** | Optional: Modal workshop (GPU credits for the fine-tune). | in person |
| **14:00** | Fine-tune go / no-go. | risk call |
| **15:00–18:00** | Human baseline on `eval-v1`: ≥ 2 people × ≥ 10 games, first attempt only. Talk to challenge mentors; put what they care about in `DECISIONS.md`. | the comparison needs real humans |
| **20:00** | G3 review: pick the 3 findings and the story with A5. | judgment |
| **20:00–23:30** | Rewrite the deck in your own words. Record the demo video and a backup screen recording. | your voice, your face |
| **Sun 00:00** | G4: call feature freeze. Open the public URL on a phone. | |
| **00:00–08:00** | *No human input needed.* Overnight runs are pre-approved within budget. | |
| **08:00–09:30** | Final check of site, deck and numbers. **Submit by 09:30.** | platform login |
| **10:30–13:00** | Peer reviewing (required). | |
| **13:00–14:00** | Rehearse the pitch twice, timed. Top 5 pitching starts 14:15. | |

---

## 8. If we fall behind

- Cut in this order: 3D rotation → ARC shim → effort ablation → live wall → `eval-v2` loop → fine-tuning.
- Never cut: solvability proof, pixels-only interface, human play, leaderboard, the recorded demo video.
- G1 missed by more than 90 minutes → A4 and A5 drop to fixtures-only polish, A3 helps A2 until the slice works.
- A provider has no key by 12:00 → it is dropped from `eval-v1`; do not hold the sweep for it.
- Shared server unreachable for 15 minutes → A2 restarts the tunnel and commits the new address. Host dead → restore the latest backup on A3's machine, which becomes the host; resumable sweeps continue from where they stopped.
- Public deploy not working by Sat 23:00 → demo runs locally, video carries the submission.

---

## Appendix A — bootstrap (Integrator, once, ~2 minutes)

```bash
set -euo pipefail
git init -b main
mkdir -p contracts scripts rules/proposals docs/research docs/deck \
  engine/src/engine engine/tests server/src/server server/tests \
  arena/src/arena arena/sweeps arena/finetune arena/tests \
  analysis/src/analysis analysis/tests web \
  data/fixtures/derived data/collections data/published \
  coordination/status coordination/requests
for p in engine server arena analysis; do
  cat > "$p/pyproject.toml" <<EOF
[project]
name = "$p"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
EOF
  touch "$p/src/$p/__init__.py"
done
for a in A1 A2 A3 A4 A5; do
  printf '# %s status\n\n## Done\n\n## Doing\n\n## Blocked\n\n## Need from humans\n' "$a" > "coordination/status/$a.md"
done
printf '# Decisions (humans only)\n\n- Project name:\n- Shared server host: A2 machine + tunnel\n- Spend cap per sweep: $5\n- Total model budget:\n- Challenge / track:\n- Final deploy host:\n' > coordination/DECISIONS.md
find . -type d -empty -not -path './.git/*' -exec touch {}/.gitkeep \;
cat > .gitignore <<'EOF'
.env
.venv/
__pycache__/
*.pyc
*.egg-info/
node_modules/
dist/
data/runs/
data/derived/
EOF
git add -A && git commit -m "bootstrap"
# then: add PLAN.md, create the GitHub remote, push main
```

On each agent machine (keeper, once):

```bash
git clone <repo-url> junction && cd junction
git switch -c agent/a<N>          # N = 1..5
mkdir -p ~/junction-data          # local dev traces only
```

## Appendix B — kickoff prompt (one per agent, in its own clone)

```
You are agent A<N> (<NAME>) on a hackathon team. Read PLAN.md completely.
Sections 1–5 bind you; your tasks are in section 6 under A<N>.
Work only inside the paths you own. Start with your P0 tasks now and keep
going through the windows without waiting for approval. Push to main after
every finished task. Update coordination/status/A<N>.md at each gate and
whenever you are blocked. You are on your own machine: other agents are
reachable only through git and through the shared server whose address is in
coordination/API_URL (section 3.4). Local dev uses DATA_DIR=~/junction-data.
Current time is in the
plan header; check the real clock before each gate.
```

| N | NAME | Branch |
|---|---|---|
| 1 | FORGE | `agent/a1` |
| 2 | GATEWAY | `agent/a2` |
| 3 | ARENA | `agent/a3` |
| 4 | STUDIO | `agent/a4` |
| 5 | LENS | `agent/a5` |
