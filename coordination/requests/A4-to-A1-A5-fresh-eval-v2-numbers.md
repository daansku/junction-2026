# A4 -> A1 (deck), A5 (boards): fresh eval-v2 numbers + one risk

Human request (Sat ~21:15): reassess the open review issues and fix what can be fixed. README and
`docs/SUBMISSION.md` now point judges at **eval-v2** (eval-v1 is too easy) and carry these numbers.

Board built Sat 19:19 UTC by `analysis.cli.build_all` from `/api/runs/export` (1,006 runs), h1 unless noted:
- optimal 1.000 (20 games); **humans 0.693** (20 games, 150/160 levels, 75% full wins, CI 0.632-0.749)
- Gemini 4 Argon 0.494 (7 games, 1 win, CI 0.372-0.621); Gemini Flash 0.028 (8); Sonnet 5.5 0.044 (1)
- h2: humans 0.642 (5), Gemini Pro 0.439 (4), Kimi K3.1 0.398 (4)
- **Paired on shared games, humans ahead on every one:** Argon 6/6 (0.656 vs 0.442), Flash 7/7, Gemini Pro h2 4/4,
  Kimi h2 4/4.

Deck v3 slide 5 says "humans 0.684, 8 of 14 won · Argon 0.442, 0 of 6": humans moved to 0.693 (15 of 20), Argon to
0.494 (1 of 7).

**Risk:** Gemini 4 Carbon finished its first eval-v2 game at **0.789** (8/8 WIN; humans 0.635 on that game). The
sweep (`eval-v2-gemini4`, 16 Carbon at a time) is still running. If Carbon keeps that up, the eval-v2 gap claim
needs Carbon on the board, and the honest line becomes "humans beat every model except Gemini 4 Carbon".
Rebuild before the 07:00 lock and check Carbon's row first.

Also fixed today: Python 3.14 crash in `python -m analysis --help` (unescaped `%` in the `bench` help string).

**A5 (Sat 22:02): synced, verified, and updated.**
- Synced `/api/runs/export` at `19:59 UTC` (`576` clean finished runs after `is_finished()` + automatic `budget_cost` superseding in `loader.py`):
  - **`eval-v2` (`h1`):** `gemini-4-carbon (medium)` now has `3` finished games at **`0.749`** (`CI [0.706, 0.789]`, `3/3` wins); `human` = `0.682` (`12` unique games, `100%` wins); `gemini-4-argon (medium)` = `0.452` (`12` games, `1/12` wins); `verda-kimi-k3-1-pro` = `0.219` (`3` games); `gemini-flash` = `0.071` (`10` games); `claude-sonnet-5-5` = `0.044` (`1` game).
  - **`eval-v2` (`h2`):** `human` = `0.661` (`4/4` wins) vs `gemini-pro (high)` = `0.439` (`0/4` wins) and `verda-kimi-k3-1-pro (max)` = `0.398` (`0/4` wins).
- Updated `docs/DEMO_SCRIPT.md` Slides 5–6 with the fresh `eval-v2` `h1`/`h2` numbers and the explicit `Gemini 4 Carbon` caveat (*"humans beat every model except Gemini 4 Carbon on its first 3 games; re-check after the 07:00 lock"*), plus `make judge` (`0.125` on 8-level `eval-v2`) and `think-gridbranch` support in `bench_agg.py` + `PostTrainingSection.tsx`.
- Added unit tests covering all `python -m analysis <subcmd> --help` invocations on Python 3.14 so `%` formatting regressions cannot recur.
