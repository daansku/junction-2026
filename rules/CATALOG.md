# Rule catalog (A1)

Every rule = one file in `engine/src/engine/components/`. Status: `live` (in generator), `wip`, `planned`.
Colours below are defaults; skin shuffle permutes object colours per game, so never rely on them.

| Rule | File | Tier | Status | Default look | Teaching level | Test |
|---|---|---|---|---|---|---|
| walls | `walls.py` | 0 | live | grey solid cell | every level | `test_core.py` |
| goal | `goal.py` | 0 | live | ring cell (skinned) | level 1 | `test_core.py` |
| move budget | `budget.py` | 0 | live | yellow bar, rows 0-1, shrinks per action | level 1 | `test_budget_game_over_and_reset` |
| keys + doors | `keys_doors.py` | 1 | live | key = small square; door = vertical bars, same colour as key. Held keys = HUD pips | door on a chokepoint, key off the path | `test_keys_doors` |
| plates + gates | `plates_gates.py` | 1 | live | plate = checker; closed gate = horizontal bar, same colour. Any plate flips every gate; gates may start open | gate on a chokepoint, plate off the path | `test_plates_gates_toggle` |
| teleporters | `teleporters.py` | 1 | live | X; stepping on one end moves you to the other | goal walled off, pair is the only way across (+ decoy pair at d>=2) | `test_teleporters` |
| hazards + health | `hazards.py` | 1 | live | plus sign; -1 health per step onto it; 0 health = level lost. Health = HUD pips in player colour | run of hazards on the shortest path as long as total health, so a detour is needed | `test_hazards_damage_and_death` |
| push blocks | `push_blocks.py` | 1 | live | ring with centre dot; pushed one cell if free behind; never into goal | blocks on the path | `test_push_blocks` |
| one-way tiles | `one_way.py` | 1 | live | arrow (shaft + bar near the head); enter only moving in that direction | arrows on the path, at least one against travel | `test_one_way` |
| ice | `ice.py` | 1 | live | diagonal stripes; keep sliding until blocked or off ice | ice patch over the path | `test_ice_slides_until_blocked` |

Every generated level is checked: BFS-solvable, **every active rule matters** (removing it changes optimal length or makes it unsolvable), random walk wins < 2%.

## Curriculum (engine 0.2.0)
Level 1 = movement + goal. Levels 2..n-1 each introduce one new rule (teaching layout: smaller grid, +8 move allowance), alone or with 1-2 seen rules. For games with >= 5 levels the last level is an "exam": 2-3 seen rules, no new rule. No two levels share a rule set. Order and combos come from the seed.

## Frame layout
- rows 0-1: move-budget bar (full width = full budget; empty part dark grey)
- rows 3-4: level pips (green done, white current, dark grey to do), then component HUD items
- rows 6-63: play area, logical grid x integer cell size, centred
- GAME_OVER: red dither over the floor; only `RESET` works
- WIN (all levels): green frame with checker band; nothing works after
