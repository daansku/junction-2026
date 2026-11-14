# Coordination board

Cross-agent work items that need more than one agent. Each item also has a file in
`coordination/requests/`; close it there (and here) when done.

## OPEN: procedural level generation on the website (A2 + A4), requested by humans Sat ~14:00

Humans want to generate new maps from the web UI ("that's the entire point of the project").
Today the UI only lists prebuilt collections (dev / eval-v1 / eval-v2 / train-v1).

**Engine (A1): ready.** `engine.make_game(GameSpec(seed=..., difficulty=1..4, n_levels=...))`
returns a verified game (solvable, every rule matters, deterministic per seed) in ~0.5-2 s.
CPU only, never a paid model call, so it is safe in published mode too.

**A2: server endpoint** (`coordination/requests/A1-to-A2-generate-endpoint.md`): **DONE in code** (A2, 14:00), in `contracts/openapi.yaml`; **live on the shared server since 14:02**. Extras: `GET /api/games?collection=generated` lists recent games; 30/min per client; 503 when busy; 422 if no valid game for a seed.
```
POST /api/games/generate  {seed?: int, difficulty: 1-4 (default 2), n_levels: 3-8 (default 6)}
  -> {game_id, ...game.describe() meta}
```
- No seed given: draw a random one in 1_000_000-9_999_999 (outside eval 900000-999999 and
  train 100000-899999) so eval games can't be previewed.
- Reject seeds 900000-999999 unless ADMIN_TOKEN (eval leak guard).
- Nothing else changes: `engine_adapter.load_game` already regenerates any game from its id
  (`gridworld-s{seed}-d{d}-l{n}-{hash}`), so `POST /sessions` with the returned id just works.
- Optional: cache the last N generated games in memory so the gallery/detail pages can show them.

**A4: UI** (`coordination/requests/A1-to-A4-new-game-button.md`)
- `/play`: a **New game** control: difficulty 1-4 (4 = 3 never-trained rules, hardest),
  levels 3-8, optional seed box, "random" button. Calls the endpoint, then starts a session
  on the returned `game_id`.
- Show the seed in the HUD/sidebar so people can share "try seed 4217 d3".
- Optional: same control on the gallery, opening the game detail page.
- **A4 status (Sat 14:15): UI done on main.** `/play` sidebar "new game" panel (difficulty 1-4, levels 3-8, seed box, Generate / Random), calls `POST /api/games/generate` with `{seed?, difficulty, n_levels}`, needs `game_id` in the response, then starts the run. Seed shown in a "this game" panel with a copy-link button. Works in mock mode; on a server without the endpoint it says so (404/405) and starts nothing; 403 shows "seed range reserved". A2's endpoint is live (14:03); A4 tested UI + endpoint end to end at 14:10 (seed 4217 d3, run started, moves work). **Left: A2 rebuilds `web/dist` on the host** so the live site has the panel. Gallery control not done.
- **A2 (Sat 14:20): `web/dist` rebuilt on the host; the panel is live.**

## OPEN: improvement plan (humans, Sat 14:10): new mechanics, failure explanations, UI upgrade

Requested by Anssi. Split by owner below; each agent also has a request file
(`coordination/requests/human-plan-to-A<n>-*.md`). **Human decision: A5 leads the UI upgrade** (see `DECISIONS.md`).
Respect the freezes: `eval-v1` stays frozen (new rules never change it), harness `h1` is frozen, feature freeze
Sun 00:00. Cut order if late: board flip, then ghost race, then X-ray curtain, then heatmap polish.

### 1. Game mechanics (A1, engine)
Already live, so only extend: teleporters (add variants: one-way, colour-linked), mirror twin (`twin.py`),
push blocks / ice / gravity (physics basics). New work:
- **Force interaction with each new mechanic:** the teaching level must be unsolvable without using the new rule
  (stronger than the current "rule matters" check: the rule-ignorant plan must be impossible, not just longer).
- **More practice between introductions:** after each teaching level, at least one consolidation level that reuses
  the rules seen so far with no new rule (more levels per game, or fewer new rules per game; A1 decides and documents
  it in `rules/CATALOG.md`). New collections only (e.g. `eval-v3`); never regenerate `eval-v1`.
- **Physics puzzles:** e.g. momentum (keep moving until blocked, off ice), falling or rolling boulders, push chains,
  blocks that slide on ice. One component file each, with a teaching level and a test.
- **Shadow player:** a follower that repeats the player's moves k steps later (distinct from the mirror twin, which
  moves at the same time). Touching it loses the level, or a rule needs it (e.g. the shadow must hold a plate).
- **Board flip (late game, very advanced, tier 3 / d4 only):** a flip tile turns the board over; the player moves on
  the reverse side, which has its own layout, and must remember their position and the hazards of the side not shown.
  Fairness check: both sides must have been visible before the player needs that memory.
- Every new rule: swatch + GIF in `rules/img/`, a row in `CATALOG.md`, solver / necessity / random-walk checks.

### 2. Why models fail: LLM failure explanations (A5 leads, A3 runs the model calls, A2 serves)
- **A5:** an `analysis` command that, per failed level, packs the level's rules, optimal path, the model's
  step-aligned `reasoning` / `hypothesis` (from `steps.jsonl`) and the truth events, asks a judge LLM which mechanic
  the model misunderstood, at which step, and what it should have done, and writes `data/derived/explanations.json`
  (fields: run_id, level, step, rule, verdict, evidence quote; claim-checked). Prompt and output defined in
  `analysis/METRICS.md`; schema addition to `contracts/derived.schema.json` through A2.
- **A3:** the judge-model call (keys are on A3's machine): a small CLI or function A5 can call, with a cost estimate
  first and within the `DECISIONS.md` budget. The judge sees the truth; playing models never do.
- **A2:** add the schema; `/api/derived/explanations.json` is served automatically once the file exists.
- **Web (A5):** show the explanation next to the failure in Replay and Insights.
- **A5 + A3 status (Sat 15:21): DONE in code on `main`.** `python -m analysis explain [--estimate|--judge-arena|--judge-cmd]` is live and wired to A3's `arena.judge.complete` (`--judge-arena`) + `trace-auditor-v1` fallback, claim-checked via `python -m analysis check-claims` (`0` errors), and rendered in both `/replay` and `/insights`. Ready for A3 to run `--judge-arena` on the Verda host after sweep completion.

### 3. UI upgrade "Epistemic Arena" (A5 leads, A4 supports, A2 adds endpoints)
Keep `web/DESIGN.md` strictly: flat dark tabular look (#0e0e0f surface, 1px `--line` hairlines, IBM Plex Mono,
#ffdc00 accent), no gradients, no glass.
- **Cartridge bezel + physics X-ray curtain** (`lib/FrameCanvas.tsx`, `features/play/PlayPage.tsx`,
  `features/replay/ReplayPage.tsx`): recessed #080809 bezel; toggleable 0..63 mono coordinate rulers (the (x, y)
  models cite in their reasoning); draggable #ffdc00 split divider: left = raw pixels ("what the model sees"),
  right = SVG ground-truth overlay ("engine truth, hidden from the agent") from `describe()` (`start_pixel`,
  `optimal_pixels` BFS path), last-5-step ghost trail, rule sprites from `rules/img/<rule>.png`, bump / slid / reset
  markers from each step's `truth.events`.
- **Live world generation + ghost race + take over** (`/play`, `/replay`, `/insights`): the New game panel already
  calls `POST /api/games/generate` (A4, done). Add a ghost-race HUD that steps recorded runs of the top models (and
  optimal BFS) on the same level in lockstep with each human keypress, streaming their step-aligned hypothesis text
  beside the board; and a `[ TAKE OVER FROM STEP N ]` button on Replay and on Insights failure clips.
- **Data pages fit 1080p above the fold** (Overview, Leaderboard, Insights). Insights: 8-col square-cell
  Rule x Player heatmap + 4-col sticky cell inspector (rule swatches, diagonal-hatched n/a cells, 4px failure-mode
  bars, `#runId · @step` replay pills). Leaderboard: full-width 4px series-coloured score underlines
  (`seriesColorFor`), grouped column headers (OUTCOME / EFFICIENCY / BEHAVIOUR), baseline line styles (solid optimal,
  long-dash human, dotted random/noop), click-to-replay scatter points.
- **Ownership for this work:** A5 keeps `features/leaderboard` and `features/insights` and, for this upgrade, takes
  `lib/FrameCanvas.tsx`, `features/play/PlayPage.tsx`, `features/replay/ReplayPage.tsx`,
  `features/overview/OverviewPage.tsx`. A4 hands over any in-flight change to those four files and stops editing them
  once A5 claims them in its status file. A4 keeps the rest of `web/` (router, design tokens, primitives, API client,
  gallery, compare, live wall), adds shared primitives A5 needs, and reviews A5's pages against `DESIGN.md`.
- **A2 endpoints for the UI: DONE in code (A2, Sat 14:45), documented in `contracts/openapi.yaml`; live on the shared server after its next restart (not during A3's sweep).** A5: exclude runs with `meta.start_level` from baselines in `analysis`. Explanations schema (`explanations` in `contracts/derived.schema.json`) is in.
  - `GET /api/games/{id}/ghosts?level=N&limit=K`: the K best recorded runs on that level as step slices only
    (action, frame, hypothesis, events), so the browser never downloads multi-MB `steps.jsonl` files.
  - `POST /api/sessions` with optional `start_level` (engine `goto_level`) for take-over; such runs carry
    `start_level` and `takeover_of: {run_id, step}` in `meta.json` so analysis keeps them out of the human baseline.
  - `GET /api/rules/img/{rule}.png` (and `.gif`) serving `rules/img/`.
- **A5 UI status (Sat 15:21): DONE on `main` (`npm run typecheck && npm run build` clean, zero cuts).** Cartridge bezel + draggable `#ffdc00` X-Ray curtain + `0..63` rulers (`FrameCanvas.tsx`, `XrayOverlay.tsx`), Ghost Race lockstep HUD + `[ TAKE OVER FROM STEP N ]` (`PlayPage.tsx`, `ReplayPage.tsx`, `InsightsPage.tsx`), 1080p Overview + Leaderboard (`4px` series bars, grouped headers, baseline dashes, click-to-replay scatter) + Insights (8-col matrix + 4-col sticky inspector, diagonal-hatched `n/a`, rule sprites, failure diagnosis cards). Ready for A4 `DESIGN.md` review and A2 `web/dist` rebuild on Verda (`95.216.229.250.sslip.io`).
