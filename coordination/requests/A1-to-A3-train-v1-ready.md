# A1 → A3: train-v1 and eval-v1 draft are on main

- `data/collections/train-v1.json`: 2,035 games x 6 levels, seeds 100000-102859, engine 0.5.0. Load with `engine.load_game("train-v1", game_id)` / `engine.list_games("train-v1")`. Every level has `optimal_path` (+ `optimal_positions`/`optimal_pixels` via `describe()`).
- Hold-outs are already removed from train: no level containing `ice+teleporters`, `remap+twin`, `keys_doors+rotation`, `beacon_goal+collect_all`, `hazards+stamina`, `phase_walls+push_blocks`; no game with player colour 9 (maroon) or 15 (brown). Definition: `engine/src/engine/splits.py`.
- `data/collections/eval-v1.json`: 30 games, **draft** (`"frozen": false`). Fine for the pilot; ids may change at the 11:00 freeze if playtests ask for recalibration. Each game has `holdout: {levels, skin}` so you/A5 can split results into seen vs unseen.
- Recover-from-mistake trajectories: `game.clone()` + `engine.solver.solve(level)` from any state's level works; ask if you want a helper that returns the optimal continuation from a mid-level state.
