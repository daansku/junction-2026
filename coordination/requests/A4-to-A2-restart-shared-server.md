# A4 → A2: restart the shared server on current main before the overnight sweep (urgent)

**What:** `GET /api/health` on the shared URL says engine **0.2.0**; main has engine 0.5.0, with different `dev` game ids. Please pull main and restart the shared server (same tunnel URL if possible; recommit `coordination/API_URL` if it changes). After that, **don't restart it until the `overnight-dev` sweep finishes** (~230 runs from A4's machine; progress in `coordination/OVERNIGHT.md`).

**Why:** the overnight sweep (human request, plan in `coordination/OVERNIGHT.md`) targets the shared server. Traces from a stale engine would not match the frozen collections or A1's describe() data.

**By when:** as soon as you read this. A4 starts the sweep when `/api/health` reports the main engine version.
