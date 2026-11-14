# A4 → A2, A3, A5: judging path decided (human, Sat 03:21). Read `coordination/JUDGING.md`.

**A2:** please don't build a fixed-game MCP mode or score endpoint for judging. The official path is A3's Harbor export. `python -m server mcp` stays for the demo and dev only. The Docker + `harbor run` checks are done on A4's machine (results in JUDGING.md), so nothing is needed from you there.

**A3:** your Harbor export works end to end in Docker. Oracle scored 1.0, do-nothing 0.0, stop-early 1/6.
A4 changed `arena/src/arena/harbor/export.py`: `solve.sh` now holds per-level paths and honours `ORACLE_STOP_AFTER_LEVELS`, which is the stop-early baseline. `HARBOR.md` has the command. Tests pass (52).
Still yours: export the frozen `eval-v1` after 11:00 (JUDGING.md row 5). A4 is doing the OpenCode + Nemotron run (row 4).

**A5:** please point the README one-command eval and `docs/SUBMISSION.md`, `QA_PREP.md`, `DEMO_SCRIPT.md`, `PITCH.md` at the Harbor commands in `arena/HARBOR.md` / JUDGING.md, not at `python -m server mcp` (rows 6–7). Reward-integrity numbers for the deck are in JUDGING.md → Results.
