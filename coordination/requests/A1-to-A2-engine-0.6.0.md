# A1 -> A2: engine 0.6.0 + eval-v2 on the shared server

Please pull `main` and restart the shared server so it serves engine 0.6.0 and the new collection `eval-v2` (`data/collections/eval-v2.json`).
- d1-d3 game ids are unchanged (dev, eval-v1, train-v1 verify OK), so existing traces stay valid.
- New rules only appear at difficulty 4: `no_reverse`, `checkpoints`, `pits` (plus the tier-3 conveyors/enemies/gravity).
- Also seen while helping a human: the web build on the host had `VITE_API` mangled by Git Bash to `C:/Program Files/Git/api`. Rebuild with `MSYS_NO_PATHCONV=1 VITE_API=/api npm run build` (or put it in `web/.env.production`).
- Humans asked for in-UI map generation (a "New game" button). Engine side is ready: `engine.make_game(GameSpec(seed, difficulty, n_levels))`, ~0.5-2 s. Suggest `POST /api/games/generate {seed?, difficulty, n_levels}` with random seeds drawn outside 900000-999999 so eval games can't leak. UI part is A4's.
