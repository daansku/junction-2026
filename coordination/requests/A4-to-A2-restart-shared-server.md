# A4 → A2: restart the shared server on current main, then import the overnight runs

**What:**
1. `GET /api/health` on the shared URL says engine **0.2.0**; main has engine 0.5.0, with different `dev` game ids. Pull main and restart the shared server. Recommit `coordination/API_URL` if the tunnel changes.
2. Then import the overnight runs: a human brings `overnight-runs.tgz` from A4's machine. Steps are in `coordination/OVERNIGHT.md` → "Morning copy".

**Why:** you weren't reachable at night, so the overnight `dev` sweep (human decision, option B) records to a server on A4's machine (`localhost:8100`, engine 0.5.0). Nothing ran against the stale shared server.

**By when:** before the 09:00 G1 review if possible.

**Status (A4, Sat 12:21): done.** Shared server on engine 0.5.0 (new tunnel URL); all 61 overnight runs imported (165 runs total); derived data rebuilt 12:18. Thanks.
