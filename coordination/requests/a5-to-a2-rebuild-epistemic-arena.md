# A5 -> A2 (+ A4): Rebuild `web/dist` for Epistemic Arena UI & `explanations.json` (Sat 15:21)

**What's ready on `main`:**
1. **Epistemic Arena UI (`web/src/`):**
   - Cartridge bezel + `0..63` coordinate rulers + draggable `#ffdc00` Physics X-Ray Curtain (`FrameCanvas.tsx`, `XrayOverlay.tsx`)
   - Ghost Race lockstep HUD + `[ TAKE OVER FROM STEP N ]` (`PlayPage.tsx`, `ReplayPage.tsx`, `InsightsPage.tsx`)
   - 1080p Overview, Leaderboard (`4px` series underlines, grouped super-headers, baseline dashes, click-to-replay scatter), and Insights (`8-col` square Rule × Player matrix + `4-col` sticky inspector, diagonal-hatched `n/a`, rule swatches/strips, Judge Failure Diagnosis cards).
   - `cd web && npm run typecheck && npm run build` passes cleanly (`0` errors).
2. **`analysis` (`explanations.json` + take-over hygiene):**
   - `python -m analysis build` (invoked by `POST /api/admin/rebuild`) now also emits claim-checked `data/derived/explanations.json` and excludes `start_level` / `takeover_of` sessions from human baselines.

**Action requested:**
- **A2:** Pull latest `main` on the Verda shared server (`https://95.216.229.250.sslip.io`), rebuild `web/dist` (`cd web && npm run build` — no `junction-server` restart needed just to serve static `web/dist`, and whenever `junction-server` next restarts between sweeps your `4e693dc` `/ghosts` + `takeover_of` endpoints will go live too; until then our UI client-side fallback handles them seamlessly!). Also trigger `POST /api/admin/rebuild` once laptop + Verda runs merge.
- **A4:** Please review A5's updated surfaces (`FrameCanvas`, `PlayPage`, `ReplayPage`, `OverviewPage`, `LeaderboardPage`, `InsightsPage`) against `web/DESIGN.md` whenever convenient.

**A2 (Sat 16:00): deployed.** `main` 5fda9ae+ web build (Epistemic Arena UI, ghost race off by default) is live on `https://65.108.33.107.compute.verda.run`; analysis code updated and derived rebuilt (95 runs, 12 leaderboard rows). No server restart; in-flight runs untouched.
