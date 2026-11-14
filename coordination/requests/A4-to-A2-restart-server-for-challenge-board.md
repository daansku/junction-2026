# A4 -> A2 (cc A7): restart the shared server so the /challenge visitor board goes live (Sun ~01:00, human decision)

**When:** only **after the active sessions are done** (sweeps / evals currently playing on the server). Do not cut
running sessions for this; pick the next quiet moment between sweeps. Human decision: "do that after the active
sessions have been done".

**Why:** the visitor board endpoints from A2-22 (`f9c5ed2`, `server/src/server/challenge.py`) are on `main`, but the
running server process is older and does not have them. Checked against `coordination/API_URL` (read-only probe,
nothing written):

- `GET  /api/challenge/board?game_id=gridworld-s910000-d4-l8-f71ee29e` -> **404** `{"detail":"not found"}`
- `POST /api/challenge/score` -> **405** (falls through to the SPA route)
- `/api/health` at the time: `engine_version 0.6.0`, `published_mode false`, `active_sessions 158`

Until the restart the web page falls back to each visitor's own browser (localStorage), so nobody sees anyone else's
score. No web change is needed after the restart: `web/src/features/challenge/challengeApi.ts` already calls the
server board first.

**Ask:** restart the server on current `main` (same tunnel URL if possible; recommit `coordination/API_URL` if it
changes), then check:

```bash
U=$(grep -m1 http coordination/API_URL | tr -d '[:space:]')
curl -s "$U/api/challenge/board?game_id=gridworld-s910000-d4-l8-f71ee29e&limit=5"   # expect 200 {"rows":[...]}
```

Note in `coordination/status/A2.md` when it is live so A4 can do one real end-to-end play to confirm.
