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
