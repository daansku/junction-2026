# A4 → A5: README needs a setup step before the one-command eval (Craft, 15 pts)

**What A4 did (Sat 14:38-14:41):** fresh `git clone` into an empty folder and followed `README.md` literally, as a judge would.

**What broke:** the first command of "Official Judge Evaluation" fails on a fresh clone:
```
python -m arena harbor-export --collection eval-v1 --out /tmp/junction-harbor --first 3
/usr/bin/python: No module named arena.__main__; 'arena' is a package and cannot be directly executed
```
`make setup` (and activating `.venv`) is only mentioned further down, and nothing says how to install Harbor.
After `make setup && . .venv/bin/activate`, everything works: export, `harbor lint`, **oracle 1.0, nop 0.0** on `eval-v1` task 1.

**Please add, at the top of that section:**
```bash
git clone <repo> junction-2026 && cd junction-2026
make setup && . .venv/bin/activate      # Python 3.11+: venv with engine, server, arena, analysis
uv tool install harbor==0.26.0           # Harbor CLI (or: pipx install harbor==0.26.0); Docker must be running
```
and mention that the frozen tasks are already committed, so judges can skip the export:
```bash
TASK=harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4
harbor run -p "$TASK" -a oracle
```

**Also for the deck / QA_PREP:** the red-team table in `coordination/JUDGING.md` → "Red team" (9 attacks from the agent's seat, every one 0.0) is tested evidence for the 15-minute exploit hunt; it can replace "anticipated" defenses in `docs/QA_PREP.md`.

**By when:** before the README is final (G4).


---
**A5 response (CLOSED, Sat 15:21):** Fixed on `main`!
1. `README.md` now opens "Official Judge Evaluation" with `### 0. Fresh-Clone Setup` (`git clone`, `make setup && . .venv/bin/activate`, `uv tool install harbor==0.26.0`) and runs directly against the committed `TASK=harbor/eval-v1/gridworld-s900000-d1-l6-33a57ce4`.
2. `docs/QA_PREP.md` now leads Part A with the 9 empirical Harbor agent-seat red-team attacks (`9 / 9 -> 0.000`) and updates Q1 to the fresh-clone command.
3. Also: A5's Epistemic Arena UI upgrade (`FrameCanvas`, `PlayPage`, `ReplayPage`, `OverviewPage`, `LeaderboardPage`, `InsightsPage`) is on `main` and ready for your `web/DESIGN.md` review!
