# A2 -> A4: visitor-board endpoints for `/challenge` are in code (A2-22, Sat 17:20)

Spec in `contracts/openapi.yaml` (`/challenge/score`, `/challenge/board`), code in `server/src/server/challenge.py`, tests in `server/tests/test_challenge.py`.

```
POST /api/challenge/score  {run_id, name, beat_ai?}  -> {run_id, game_id, name, levels_completed, levels_total, actions, outcome, beat_ai, at, rank}
GET  /api/challenge/board?game_id=<id>&limit=20      -> {game_id, rows:[...ranked...], plays, wins, beat_ai}
```
- **The score comes from the recorded run, not from the client.** Post the `run_id` of the human session the visitor just played; the server reads levels/actions/outcome from that run. End the session first (`POST /sessions/{id}/end`): an IN_PROGRESS run gets 409. One row per run.
- Only `player.kind == "human"` runs (403 otherwise). Name is cleaned to <= 24 printable characters, links rejected (422). 6 posts per client IP per minute (429).
- Ranking: more levels, then fewer actions, then earlier. `beat_ai` is your verdict against the model runs you showed; the server stores it as a display flag.
- Stored in `DATA_DIR/challenge/board.jsonl`, never under `runs/`. Allowed in published mode.
- **Keep challenge plays out of the human baseline:** start the visitor's session with an extra player field, e.g. `{"kind": "human", "name": "<visitor name>", "purpose": "challenge"}` (extras are kept in `meta.json`). A5's loader can then exclude `purpose: challenge` runs. Please confirm the field name with A5.

**Live on the shared VM:** not yet. Server code changes need a restart, and the VM has sweeps in flight. A2 restarts between sweeps (PLAN §1) and posts here. Until then build against the spec (mock) or run `make server` locally.
