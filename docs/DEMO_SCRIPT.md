# Live Demo Choreography (`docs/DEMO_SCRIPT.md`)

> **Total demo slot:** 10 minutes + 15-minute live judge exploit hunt.
> **Rule:** Never show a slide where a live `/replay/<run_id>?step=<step>` tab or CLI check can show real ground-truth behavior.

---

## Pre-Demo Verification Checklist (T-15 min)

Run these commands cleanly and verify exit code `0` before walking onto stage:

```powershell
# 1. Verify tests and claim-check consistency
$env:PYTHONPATH="analysis/src"
python -m unittest discover -s analysis/tests -v
python -m analysis check-claims --derived data/fixtures/derived

# 2. (If live server traces exist) Sync + rebuild live derived files & check claims
python -m analysis sync --data-dir ~/junction-data
python -m analysis build --data-dir ~/junction-data --with-fixture-baselines --write-proposals
python -m analysis check-claims --derived ~/junction-data/derived

# 3. Verify web bundle compiles cleanly
cd web
npm run typecheck
npm run build
```

Keep 4 browser tabs pre-loaded and zoomed to `110%` on a dark display (`web/DESIGN.md` canvas):
1. Tab 1: **Deck** (`docs/deck/index.html`) — architectural framing only (Slides 1–2 & Final Slide).
2. Tab 2: **Play & Gallery** (`/gallery` → `/play/<game_id>`) — live interactive pixels-only human play.
3. Tab 3: **Leaderboard** (`/leaderboard`) — Action-Efficiency Frontier + Reward Integrity KPI strip.
4. Tab 4: **Insights & Replay** (`/insights`) — click an evidence chip directly into `/replay/fixture-run-0001?step=10` (or live frontier failure step).

---

## Beat-by-Beat Run of Show (10 Minutes)

| Time | Screen | Presenter Action & Exact Spoken Point |
|---|---|---|
| **0:00 – 1:15** | **Tab 1 (`docs/deck/index.html` Slide 1–2)** | Frame the AfterQuery question: *"Static text benchmarks reward guessing and memorization. We built a procedurally seeded 64×64 pixel RL curriculum where zero rules are written in prose, object colors shuffle per game (`skin_shuffle`), and every action is priced against an exact BFS shortest path."* |
| **1:15 – 3:00** | **Tab 2 (`/gallery` → `/play`)** | Open a generated game live and make 4–5 keyboard moves (`Arrow` / `WASD` + `R` reset). Point out the pixel HUD (`rows 0–1` move-budget bar shrinking per step, `rows 3–4` level pips, inventory/health pips) and prove that no text tutorial or JSON `truth` exists in the client network response. |
| **3:00 – 5:00** | **Tab 3 (`/leaderboard`)** | Walk through the top KPI strip and Cost-vs-Score Frontier plot. Point out: *(a)* `Optimal` baseline sits at `1.000`, *(b)* `Mock Model` / frontier agents leave a clear efficiency gap (`0.252` on fixture run `fixture-run-0001`), *(c)* `Random` scores `0.008`, and *(d)* **`noop` and `stop_early` score strictly `0.000`** (`VERIFIED ZERO-EXPLOIT` chip). Toggle `Show Table` to prove every chart dot matches exact token/cost/action figures. |
| **5:00 – 7:30** | **Tab 4 (`/insights` → click `@step 10` → `/replay/fixture-run-0001?step=10`)** | On Insights, inspect the **Rule × Player Discovery Matrix** (toggle `Recombined solve rate` vs `Wasted actions`) and **Failure Taxonomy**. Click the `no_effect_loop` or `late_reset` evidence chip to jump straight into Replay at `step=10` and `step=11`: show the model's live `hypothesis`, `belief`, wall bump event, and delayed `RESET` burning budget. |
| **7:30 – 9:00** | **Terminal (`MCP` + `check-claims`)** | Show Harbor/OpenCode MCP readiness (`python -m server mcp --help`) and run `python -m analysis check-claims` in terminal to prove zero mismatch between derived JSON, UI numbers, and trace logs, plus show the generated `rules/proposals/auto-*.md` feeding `eval-v2`. |
| **9:00 – 10:00** | **Tab 1 (Final Slide)** | Summarize the 4 AfterQuery rubric proofs (`Gap`, `Meaningful Difficulty`, `Reward Integrity`, `One-Command Craft`) and invite judges to begin the 15-minute exploit hunt + live Harbor/OpenCode rerun. |

---

## Backup Plan if Network / Tunnel Drops Live

- `web/` runs seamlessly offline against committed fixtures (`data/fixtures/derived/*.json` + `data/fixtures/runs/*`) via `MockApi` (`VITE_MOCK=1`).
- Start a throwaway local backend if needed:
  ```bash
  make server PORT=8000
  ```
- Every formula, schema validator, and fixture score can be reproduced locally in `< 2s` with zero API keys via `python -m unittest discover -s analysis/tests -v`.
