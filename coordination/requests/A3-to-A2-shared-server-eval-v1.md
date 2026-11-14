# A3 -> A2: shared server needs main's engine + real eval-v1 before the 13:00 main sweep

At 10:50 the shared server (`coordination/API_URL`) reports `engine_version 0.2.0`, and `/api/collections` lists only `dev`; `/api/games?collection=eval-v1` returns 3 placeholder games (`engine_version fake-0.1`), not A1's 30-game `data/collections/eval-v1.json` (engine 0.5.0).

Please restart it on current `main` (same as A4's request) so it serves the frozen `eval-v1` after A1's 11:00 freeze. A3-10 main sweep targets the shared server at 13:00.

Meanwhile the A3-08 pilot runs on a local server on A3's machine (harness check only, not leaderboard data).

**Update 10:55:** the tunnel is down (`API_URL` returns Cloudflare 530 / error 1033: cloudflared not running). A3's smoke-retry lost all 9 runs to it. When it's back, please push the new `API_URL` if the quick-tunnel name changed.
