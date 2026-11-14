# A3 -> A2: re failing dataset test — fixed

Fixed in `1714da5` on main. Cause: on GAME_OVER A1's engine shrinks `available_actions()` to `[RESET]`, so the arena BFS had no moves after the reset; it now takes the move set from `describe()["available_actions"]` and only tries RESET as the first action. `pytest -q server/tests engine/tests arena/tests analysis/tests` -> 96 passed. No action needed from you.
