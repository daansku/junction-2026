# A4 -> A2: visitor-board endpoints for /challenge (A2-22) + deploy (A2-23)

**What:** `/challenge` (and `/kiosk`, same page without the top bar) is on `main`. It already calls these two endpoints and falls back to a per-browser board when they 404, labelled "this device only". Please add:

1. `POST /api/challenge/score`, body:
   ```json
   {"game_id": "gridworld-s1000-d1-l6-9b1065f8", "name": "Anna", "score": 87.3, "cleared": 3, "moves": 51, "beat_ai": true, "at": "2026-11-14T17:40:00Z", "run_id": "20261114T..."}
   ```
   - `name`: 1-20 chars, letters/digits/space/`_.-` only (the client already strips the rest; please re-check server side). No other free text.
   - `score` 0-100, `cleared` 0-10, `moves` 0-2000. Reject anything else with 422.
   - Ideally recompute `score`/`cleared`/`moves` from `run_id` (session run on the server, `player.mode == "challenge"`), so the board cannot be forged with curl. If no time: store as sent, it is a fun board, not research data.
   - Rate limit per IP (e.g. 1 per 10 s). Allowed in published mode.
   - Store apart from runs (e.g. `DATA_DIR/challenge_board.jsonl`), never in `runs/`.
2. `GET /api/challenge/board?game_id=...&limit=10` -> `{"entries": [ ...same objects, best first... ]}`. Sort: score desc, cleared desc, moves asc.

**Visitor sessions:** created as `player: {kind: "human", name, mode: "challenge"}` (extra field, kept by `PlayerIn`). They must not count as human baseline; A5 is asked to filter them in `analysis` (`A4-to-A5-challenge-runs-filter.md`). If `/runs` or the ghost endpoint can skip `player.mode == "challenge"` too, even better.

**Deploy (A2-23):** rebuild `web/dist` on the VM after pulling (no server restart needed for the page itself). Public URLs to test: `/challenge` and `/kiosk`. The page reads `web/public/challenge/<game_id>.json` (committed, regenerate with `python web/scripts/challenge_stats.py --api <origin> --game <id>` before the 07:00 lock).

**Why:** PLAN.md §3.4, A2-22/A2-23. **By when:** H2 (Sat 23:30).

**A2 (Sat 17:45):** endpoints are on `main` (f9c5ed2) and your client (`challengeApi.ts`: `{run_id, name, beat_ai}` in, `rows` out) matches them, so nothing changes on either side. Visitor sessions with `player.mode: "challenge"` are fine (extras are kept in meta). Live on the VM at the next restart between sweeps (63 sessions in flight at 17:45); the page itself goes live with the next `web/dist` rebuild (no restart). A2 posts here when both are live.
