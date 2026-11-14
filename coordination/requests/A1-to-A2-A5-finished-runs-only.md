# A1 -> A2, A5: boards count finished attempts only (human decision, Sat ~20:30)

**Human request:** "on the website all attempts are counted towards the leaderboard but only ones that were finished
should (either ran out of moves / budget or won the game)".

**Done (A1, `analysis/src/analysis/loader.py`, small and isolated):** `is_finished()` in `filter_benchmark_runs`.
A run counts only if its outcome is `WIN`, `GAME_OVER` (a level ran out of moves) or `BUDGET`. Abandoned human runs no
longer count (`ABORTED` with left_page / switched_game / gave_up / restarted). Neither do model or infra aborts.
Exception: an `ABORTED` baseline counts unless infra ended it, because do-nothing and stop-early end on purpose.
New test `analysis/tests/test_finished_only.py`; A5's `test_run_hygiene_filtering` still passes.
Effect on the 652-run export: eval-v2 humans 0.684 / 8 of 14 won -> **0.699 / 8 of 13 won**; model rows unchanged.

**A2, please:** pull main on the VM and run `POST /api/admin/rebuild` (the live board is still the 16:22 UTC build, so
abandoned attempts and older runs still show). A timer for the rebuild (every 10-15 min) would keep the site current.

**A5, FYI:** `loader.py` was not in your active-edit list; if you have local changes there, keep `is_finished()`.
`test_cli_build_and_check_claims_failure` fails on Python 3.14 only: argparse rejects a help string with a bare `%`
("unsupported format character 'C'"); write it as `%%`. The VM (3.12) is not affected.
