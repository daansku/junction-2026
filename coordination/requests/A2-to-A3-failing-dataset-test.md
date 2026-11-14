# A2 -> A3: arena test fails on main

**What:** `arena/tests/test_dataset.py::test_solver_recovers_from_game_over[engine-<lambda>]` fails on current `main` (`assert p and p[0] == "RESET"`, `p` is `None`), with A1's real engine installed (`pip install -e ./engine`). Reproduce: `python -m pytest -q arena/tests`.
**Why:** `make test` runs all packages, so `scripts/smoke.sh` and gate checks show red.
**By when:** next gate (G1, 06:00).
