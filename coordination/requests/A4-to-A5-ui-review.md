# A4 → A5: review of the Epistemic Arena UI (`35fb581`, `fbae3fd`), Sat 16:15

Checked: `npm run typecheck` + `npm run build` (pass), the handover behaviours in code, a `DESIGN.md` scan, and every page in
the browser at 1920×1080 against the new shared host.

## Update 16:35 (human): ghost race is now a presentation toggle
A4 changed `PlayPage.tsx` at the human's request (one hunk, `ghostRaceOn`): **off by default**, the toggle is remembered per
browser (`localStorage.ghostRace`), so the demo laptop keeps it on. Nothing else in your files touched. This also covers the
small baseline ask below.

## Update 16:25 (human): not a blocker
The ghost race is a visualisation; the models are the main result. Keep it, deploy as is. One small ask only: runs where a
human had the ghost race or X-ray on shouldn't count as human baseline: either default `ghostRaceOn` to `false`, or tag
such runs (`player.assisted: true`) so `filter_benchmark_runs()` can skip them. Low priority.

## (Original note, downgraded) Ghost race and the human baseline
`PlayPage.tsx:130` `const [ghostRaceOn, setGhostRaceOn] = useState(true)`. During a **recorded** human run on the shared server
the sidebar shows, before the first key press, "BFS optimal · N moves" for the level, and the best model runs' frames stepping
along with every key, their actions, events, hypotheses and "SOLVED @N". Seen on `/play/gridworld-s1003-d1-l6-6744021d`:
optimal 10 moves, Kimi's 10-action solve stepping beside the player. Once the main sweep lands on the new host, every eval-v1
game shows this. A playtester can copy a solved model run, so their run is no longer a human baseline.
The X-ray curtain (`xraySplit`, off by default, shows `optimal_pixels`) has the same problem when switched on mid-run.

Fix, in order of preference:
1. On the shared server, outside take-over mode, hide the ghost race and the X-ray **until the current run has ended**
   (win, game over or switched game). Afterwards they work as a "race replay" against your own run.
2. At minimum: default `ghostRaceOn` to `false`, and if the player switches either one on during a recorded run, record it
   (`player.assisted: true` on `POST /sessions`, or a new session; A2 keeps extra player fields in `meta.json`) and
   have `filter_benchmark_runs()` drop assisted runs from the human baseline.
Keep both free in mock / local mode, for the name `test`, and in take-over mode.

**Clean so far:** no human eval-v1 run used this build. The live site doesn't have it yet (no "ghost race" in the bundle), and
all human eval-v1 runs (12:30-14:46) predate `35fb581`. The hold request to A2 is withdrawn (human decision 16:25).

## P2: minor
- Leaderboard page is 1783 px tall and Insights 4096 px at 1920×1080; the plan asked for the data pages to fit above the
  fold. The KPI strip and the scatter are above the fold, so this is fine for the demo; only fix it if there's time.

## Passed
- Handover behaviours all present: name required on the shared server (take-overs exempt), one move at a time + 120 ms
  cooldown, "already played" marking + next-unplayed link, runs closed on win / switch / `pagehide`, New game panel, truth
  overlay off by default, touch d-pad, published-mode handling; Replay `?step=` deep link, live follow, keyboard; Overview
  error state + no Live link in published mode.
- `DESIGN.md`: no gradients, glass, emoji or new fonts; radii ≤ 2px; the only raw colours are the plan's `#080809` bezel and
  contrast fallbacks.
- `FrameCanvas` rewrite stays backward compatible: Compare (3 frames at 448 px), the Live wall and Gallery render as before.
- No console errors on Overview, Leaderboard, Insights, Gallery, Compare, Live, Play.
