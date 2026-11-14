# Coordination board

Cross-agent work items that need more than one agent. Each item also has a file in
`coordination/requests/`; close it there (and here) when done.

## OPEN: procedural level generation on the website (A2 + A4), requested by humans Sat ~14:00

Humans want to generate new maps from the web UI ("that's the entire point of the project").
Today the UI only lists prebuilt collections (dev / eval-v1 / eval-v2 / train-v1).

**Engine (A1): ready.** `engine.make_game(GameSpec(seed=..., difficulty=1..4, n_levels=...))`
returns a verified game (solvable, every rule matters, deterministic per seed) in ~0.5-2 s.
CPU only, never a paid model call, so it is safe in published mode too.

**A2: server endpoint** (`coordination/requests/A1-to-A2-generate-endpoint.md`): **DONE in code** (A2, 14:00), in `contracts/openapi.yaml`; live on the shared server after its next restart (check `/api/collections` lists `generated`). Extras: `GET /api/games?collection=generated` lists recent games; 30/min per client; 503 when busy; 422 if no valid game for a seed.
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
