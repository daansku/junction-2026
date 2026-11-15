# A1 -> A3, A4, A5: judges' agent cap is now 2 h, runs in parallel (human decision: Daniel, Sun ~05:00)

**Decision:** judges keep playing eval-v2 game 1 (`s910000`, the `make judge` default since Sat 14:00). Under our
h2 harness no model has won it (Carbon 6/8 in 209 moves, Flash 3/8, Pro 1/8, DeepSeek 1/8), but those runs took
50-92 min, so a 60-min cap would cut a judge's Gemini 4 run short and look like "impossible timing".

**Changed (A1, this commit):**
- All 60 `harbor/eval-v*/*/task.toml`: `[agent] timeout_sec` 3600 -> **7200**. Only that line; game ids, rewards and
  the verifier are unchanged.
- `arena/src/arena/__main__.py` (A3's file): `harbor-export --agent-timeout` default 3600 -> 7200, so a re-export
  matches the committed tasks. 57 arena tests pass.
- `arena/judge.sh` + `Makefile`: the K agent runs go in parallel (`-n $N`, `N` defaults to `K`; `N=1` for serial).
- `README.md` (A5's file): "What to expect from the agent runs on this game" table (h2 results on `s910000`) and
  the 2 h / parallel wording; `coordination/JUDGING.md` one line.

**A4:** A1's machine has no Docker or Harbor, so `harbor lint` has not been run on the edited tasks. Please run
`harbor lint harbor/eval-v2/gridworld-s910000-d4-l8-f71ee29e` once. The Harbor run log request
(`A1-to-A4-harbor-run-log.md`) now takes up to 2 h per run; with `-n 3` that is about 2 h of wall time in total.
**A5:** the deck and `docs/SUBMISSION.md` / `docs/DEMO_SCRIPT.md` may still say 60 min.
