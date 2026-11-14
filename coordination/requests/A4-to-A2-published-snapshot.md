# A4 → A2: fill `data/published/` before the public demo goes up

**What:** A4 tested published mode locally (Sat 12:55, `PUBLISHED_MODE=1`, built `web/dist` from main). Server side is right: model and baseline sessions get 403, `/admin/rebuild` 403, human play works and is not listed in `/runs`; the UI shows the snapshot banner and hides Live.

But `data/published/` is empty on main, so in published mode:
- `/api/runs` is `[]`: Replays, Compare, the Overview showcase and per-game results in the Gallery are all empty.
- `/api/derived/leaderboard.json` falls through to `data/fixtures/derived/`, so the public leaderboard and insights would show **fixture numbers**, not real ones.

Please commit a snapshot before the public URL goes live (G4, Sun 00:00), and refresh it at the 07:00 number lock:
- `data/published/runs/<run_id>/{meta.json,steps.jsonl}`: the runs that count (eval-v1 sweep, human baseline, baselines). Leave out `test` / `anonymous` players and ABORTED test runs.
- `data/published/derived/{leaderboard,rules,insights}.json` from A5's build over those runs.

Optional, server side: in published mode, return 404 for a missing derived file instead of falling back to fixtures, so a missing snapshot is visible rather than showing fake numbers.

**Why:** the public demo URL is what peer reviewers and judges open.

**By when:** G4 (Sun 00:00), refreshed at 07:00.
