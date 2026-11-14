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
| collect all | `collect_all.py` | 2 | live | diamond gems; goal only counts once all are collected; HUD pips | gems far from the path | `test_collect_all_gates_goal` |
| phase walls | `phase_walls.py` | 2 | live | solid square / hollow corners when open; solid for k actions, open for k (k=3-5), bumps count | on a chokepoint | `test_phase_walls_cycle` |
| rotation trigger | `rotation.py` | 2 | live | triangle; stepping on it turns the map 90 deg clockwise on screen, controls stay screen-relative | on the path | `test_rotation_*` |
| control remap | `remap.py` | 2 | live | half-filled square; toggles a per-level scramble (mirror h/v, swap axes, reverse); HUD pip lit while scrambled | on the path (+ decoy) | `test_remap_mirror` |
| mirror twin | `twin.py` | 2 | live | small square + ring goal in its own colour; copies every move (mirrored L/R at d>=2), walls stop it; win needs both on goals | twin start/goal placed apart | `test_twin_*` |
| stamina | `stamina.py` | 2 | live | every action costs 1; 0 = lost; refill pads restore to max (single use); HUD meter | refills off the path | `test_stamina_and_refill` |
| cracked floor | `cracked_floor.py` | 2 | live | X tile; holds once, collapses to a dark hole when you step off | on the way to a key/gem/plate; **taught only with collect_all, keys_doors or plates_gates** (`requires`) | `test_cracked_floor_*` |
| beacon goal | `beacon_goal.py` | 2 | live | extra goal rings; real goal wears a fresh colour, a decoy wears the game's usual goal colour; HUD beacon pip = real colour; decoy sends you to start | decoy on the shortest path | `test_beacon_decoy_sends_home` |

Proposals: `a5-decoy-and-camouflage` -> beacon_goal; `a5-delayed-state-switch` -> phase_walls; `auto-01` -> cracked_floor; `auto-02` -> collect_all; `auto-03` -> twin. `a5-sokoban-deadlock-box`: covered by push_blocks + the necessity check (the rule-ignorant plan must fail); no dedicated deadlock generator yet.

## Skins (A1-12)
Per game, by seed: object colours AND shapes are shuffled (distinct within a game). Fixed: floor, wall, budget bar, player = solid square, goal-like rings, arrows, HUD meters.

Difficulty 1 games use tier 1 only; difficulty 2-3 draw from tiers 1-2.

Every generated level is checked: BFS-solvable, **every active rule matters** (a player who ignores it has a longer/impossible optimum, or their optimal plan fails on the real level), random walk wins < 2%.

## Curriculum (engine 0.4.0)
Level 1 = movement + goal. Levels 2..n-1 each introduce one new rule (teaching layout: smaller grid, +8 move allowance), alone or with 1-2 seen rules. For games with >= 5 levels the last level is an "exam": 2-3 seen rules, no new rule. No two levels share a rule set. Order and combos come from the seed.

## Frame layout
- rows 0-1: move-budget bar (full width = full budget; empty part dark grey)
- rows 3-4: level pips (green done, white current, dark grey to do), then component HUD items
- rows 6-63: play area, logical grid x integer cell size, centred
- GAME_OVER: red dither over the floor; only `RESET` works
- WIN (all levels): green frame with checker band; nothing works after
