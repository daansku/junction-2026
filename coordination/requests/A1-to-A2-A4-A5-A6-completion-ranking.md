# A1 -> A2, A4, A5, A6: boards now rank completion first (human decision, Sat ~23:45)

Decision in `coordination/DECISIONS.md` ("Board ranking: completion first"): rank by **games won**, then **levels solved**,
then **efficiency** (the old `score`) as the tiebreak. Disclosed as post-hoc. Harbor / RL reward unchanged.

- Done (A1, on main): `web/src/features/leaderboard/ranking.ts` used by the h1 board, the h2 board and the front page;
  the "Score" column is now "Efficiency" and comes after Games Won / Levels Won; KPI tiles show games won.
  eval-v2 h1 order now: humans (73% won) > Gemini 4 Carbon (56%) > Argon (10%) > Kimi, Flash, Sonnet (0%).
- **A2:** VM `git pull`, web build, board rebuild (also picks up the h2b fix, fd62a31).
- **A4:** if any page you own still sorts or headlines by `score`, switch it to `completionCompare` / `bestByCompletion`.
- **A5:** `insights.json` texts and `analysis/METRICS.md` that call `score` "the headline" should say "efficiency"; the
  h2b board (requested in A1-to-A2-A3-A5-h2b-board.md) uses the same ranking.
- **A6:** gap scenes show games won first; efficiency as a second number.

## Update ~00:20: A1 did the A4 / A5 / A6 parts itself (human: "override and do all of those yourself")
- A4/A5 web: completion-first on h1, h2, front page; new "Extended, multi-move" tab for h2b; every "Score" label is
  now "Efficiency"; model cards show games won first.
- A5 analysis: `leaderboard_h2b.json` built by `build_all`; rows sorted completion first; best model and the efficiency
  insight lead with games won; METRICS.md note.
- A6 video: `scenes/s2_gap.py` bars = games won (ordered completion first), efficiency as a small second number; reference
  line "optimal play wins 100%"; NUMBERS.md row updated. **A6: please re-render S2** (I can't render Manim here).
- **Still open, needs SSH/admin on the VM (A2 or a human):** `git pull`, `cd web && npm install && npm run build`,
  `POST /api/admin/rebuild`. Until then the live site shows none of this.
