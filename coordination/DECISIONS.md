# Decisions (humans only)

- Project name:
- Shared server host: A2 machine + tunnel
- Spend cap per sweep: $20
- Total model budget: $300 (raised Sat 13:55; about $5 spent before)
- Challenge / track:
- Final deploy host:

## Main sweep on eval-v1 (approved Sat 13:55, recorded by A4 for the human)
- Approved up to **$210** for the sweeps below, above the $20 per-sweep cap: A3 runs them with `--approve-cost`. Details and the per-sweep breakdown: `coordination/requests/A4-to-A3-main-sweep-approved.md`.
- All 30 games x 3 attempts: Claude Haiku 5.5, Gemini Flash, DeepSeek V3.2 (featherless), baselines.
- Subsets, 1 attempt: Kimi K3.1 on 10 games, Claude Sonnet 5.5 on 10 games, Claude Opus 5.5 on 5 games. Marked as subsets on the leaderboard.
- Nemotron is not in the eval-v1 sweep (endpoint takes ~30 s per request, one game ~3.3 h); it is reported from the overnight dev run only.
- Update Sat 14:45 (human): Nemotron runs a small eval-v1 subset after all, from A4's machine: `arena/sweeps/main-subset-nemotron.yaml`, first 3 games x 1, one request at a time, 4 h wall cap per game, Verda credits. A3: don't run Nemotron elsewhere at the same time (the endpoint only queues).
- Wall cap 3 h per run, `max_actions` 400 is the budget, so scores don't measure API latency.

## Improvement plan (Sat 14:10, Anssi; recorded by A2 for the human)
- New mechanics, LLM failure explanations and the "Epistemic Arena" UI upgrade: plan and split in `coordination/COORDINATION.md`.
- **A5 leads the UI upgrade.** For this work A5 takes over `web/src/lib/FrameCanvas.tsx`, `features/play/PlayPage.tsx`, `features/replay/ReplayPage.tsx` and `features/overview/OverviewPage.tsx` from A4; A4 supports and reviews.
