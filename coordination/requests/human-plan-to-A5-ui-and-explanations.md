# Human -> A5: UI upgrade lead + LLM failure explanations (Sat 14:10)

**What:** sections 2 and 3 of the improvement plan in `coordination/COORDINATION.md`.
1. Failure explanations: an analysis command that writes `data/derived/explanations.json` (judge LLM run through A3), shown in Replay and Insights.
2. UI upgrade "Epistemic Arena": cartridge bezel + X-ray curtain, ghost race + take over, 1080p heatmap and leaderboard upgrades. You take over `web/src/lib/FrameCanvas.tsx`, `features/play/PlayPage.tsx`, `features/replay/ReplayPage.tsx` and `features/overview/OverviewPage.tsx` from A4: claim them in your status file first; A4 hands over. Follow `web/DESIGN.md` strictly.

A2 adds the endpoints you need (ghost slices, take-over sessions, rule images); ask through a request file if you need more.
**Why:** humans want the gap between human intuition and model blindness to be visible in the UI, and a clear reason for every failure.
**By when:** X-ray curtain and explanations by G3 (Sat 20:00); the rest before the Sun 00:00 freeze. Cut order if late: ghost race, then X-ray curtain, then heatmap polish.
