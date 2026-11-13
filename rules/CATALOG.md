# Rule catalog (A1)

Every rule = one file in `engine/src/engine/components/`. Status: `live` (in generator), `wip`, `planned`.
Colours below are defaults; skin shuffle permutes object colours per game, so never rely on them.

| Rule | File | Tier | Status | Default look | Teaching level | Test |
|---|---|---|---|---|---|---|
| walls | `walls.py` | 0 | live | grey solid cell | every level | `test_core.py` |
| goal | `goal.py` | 0 | live | ring cell (skinned) | level 1 | `test_core.py` |
| move budget | `budget.py` | 0 | live | yellow bar, rows 0-1, shrinks per action | level 1 | `test_budget_game_over_and_reset` |

Tier 1 (keys+doors, plates+gates, teleporters, hazards+health, push blocks, one-way, ice) next, A1-07.

## Frame layout
- rows 0-1: move-budget bar (full width = full budget; empty part dark grey)
- rows 3-4: level pips (green done, white current, dark grey to do), then component HUD items
- rows 6-63: play area, logical grid x integer cell size, centred
- GAME_OVER: red dither over the floor; only `RESET` works
- WIN (all levels): green frame with checker band; nothing works after
