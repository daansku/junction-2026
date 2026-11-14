# A1 -> A2: POST /api/games/generate (humans asked, high priority)

Full spec in `coordination/COORDINATION.md` (section "procedural level generation").
Short: add `POST /api/games/generate {seed?, difficulty, n_levels}` that calls
`engine.make_game(engine.GameSpec(seed=..., difficulty=..., n_levels=...))` and returns
`{game_id, ...}`. Random seeds from 1_000_000-9_999_999; refuse 900000-999999 without
ADMIN_TOKEN. Existing session/play routes already accept the returned id. Please also add it
to `contracts/openapi.yaml` so A4 can build against it.
