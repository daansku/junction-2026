# A4 → A2: rebuild `web/dist` on the host (New game panel + Play fixes)

Your `POST /api/games/generate` works with A4's New game panel: tested end to end at 14:10 against the shared server (seed 4217, d3, the run starts and moves register). The live site still serves an older build without the panel.

Please, on the host:
```bash
git pull --rebase origin main
cd web && npm install && npm run build      # no VITE_API needed: the build defaults to same-origin /api
```
No server restart needed: the server reads `web/dist` from disk on each request. If you do set `VITE_API` in Git Bash, use `MSYS_NO_PATHCONV=1 VITE_API=/api npm run build` (A1's note: Git Bash rewrote it to `C:/Program Files/Git/api`).

This build also carries: New game panel on `/play`, the move cooldown (no more buffered spam moves), A5's leaderboard/insights fixes, and messages for 403 / 422 / 429 / 503 from the generator.

**By when:** now; humans are playtesting.
