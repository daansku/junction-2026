# /challenge QA (A4-21, Sat 14.11 ~19:10)

Run: `python web/scripts/qa_challenge.py [BASE_URL] [OUT_DIR]` (headless Chromium via Playwright; real sessions as `test`).
Public URL `https://65.108.33.107.compute.verda.run` (build `index-3p3w2_6B.js`) and the local production build of `main`.

| Size | Frame while playing | Horizontal scroll | Notes |
|---|---|---|---|
| Projector 1920×1080 | 704 px (11×) | none | result card top right; end screen fits except the table (scroll 124 px) |
| Projector 1280×720 | 448 px (7×) | none | lobby 914 px tall: Play button at y=496, on screen |
| Laptop 1366×768 | 448 px | none | |
| Tablet 768×1024 | 704 px | none | d-pad under the frame |
| Phone 390×844 @3x | 320 px (5×) | none | d-pad at y=542, on screen with the frame |
| Phone 360×740 @3x | 256 px (4×) | none | |

Flows checked at 1080p: lobby → level 1 solved → level 2 lost by running out of moves (35-move budget) → "Retry level"
(R) → level 2 solved (39 moves incl. the lost attempt) → level 3 → end screen ("You beat the AI", 5 AI replays,
board). Phones: the same with touch taps on the d-pad. Kiosk (`/kiosk`): no top bar; 66 s without input → lobby,
name cleared; "reset kiosk" works. Load < 1 s everywhere. Console: only the expected board 404/405 (board endpoints
not on the VM yet; the per-device board is used and labelled).

Move latency on the public server while sweeps run: `act` median ~65 ms (max ~150), `truth` ~7 ms; with the 120 ms
cooldown a player gets 6-8 moves/s. Presses during a pending move are dropped (no buffering, by design).

**Bug found and fixed (`main`, not yet on the VM):** on phones and tablets the level-solved screen stacked the AI replays
first, so the "Next level" card sat at y≈2140 of a 2360 px page, out of sight. Now the card comes first on narrow
screens (y=196 on a 390 px phone). Needs the next VM web rebuild.
