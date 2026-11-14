# A7 interaction audit (Sat ~20:45, FORCE_VERSION 1, K = 2.0)

Tool: `python engine/tools/interaction_audit.py --collection <name>` or `--family gridforce --difficulty d --seeds a:b`.
Definitions (`engine/src/engine/generator/interaction.py`):
- **use rules** (keys/doors, plates, teleporters, push blocks, ice, one-way, phase walls, rotation, remap, stamina,
  conveyors, gravity, pits): *avoider score* = optimal / (shortest win that never triggers the rule), 0 if avoiding is
  impossible. Forced = avoider score <= 1/K = 0.5.
- **avoid rules** (hazards, beacon decoy, cracked floor, enemies): forced = the rule-ignorant optimal plan is
  strictly shorter than the real optimum, so it fails on the real level and the player must detour.
- builtin (collect_all, checkpoints, twin) always forced; no_reverse skipped.

## Before: current frozen collections (`gridworld`)

| Collection | Use-rule pairs | Avoider >= 0.8 | Avoider >= 0.5 | New rule forced |
|---|---:|---:|---:|---:|
| dev (10 games) | 56 | 27% | 27% | 70% |
| train-v1 (first 200 games) | 1,260 | 23% | 26% | 68% |
| eval-v1 (30) | 193 | 28% | 31% | 66% |
| eval-v2 (30, d4) | 235 | 35% | 36% | 67% |

eval-v1 teaching levels, avoider >= 0.8: **one_way 91%, push_blocks 71%, remap 60%**, rotation 11%, ice 7%;
keys/doors, plates, teleporters, phase walls, stamina 0%. Avoid rules forced under the strict definition:
hazards 44%, beacon 57%, cracked floor 0%.

## After: `gridforce` (20 fresh games per difficulty, seeds 920000-920019)

| Difficulty | Use-rule pairs | Avoider >= 0.8 | Avoider >= 0.5 | New rule forced |
|---|---:|---:|---:|---:|
| d1 | 132 | 5% | 5% | **100%** |
| d2 | 116 | 3% | 3% | **100%** |
| d3 | 126 | 3% | 3% | **100%** |
| d4 (8 levels) | 174 | 8% | 8% | **100%** |

The remaining 3-8% are older rules on a level (soft requirement, relaxed after 20/40 attempts), never the new rule.
Generation: median ~0.7 s (d1) to ~2.7 s (d4) per game, max ~7 s; 0 failures in 140 games.
Frozen collections regenerate byte-identical (engine tests: 135 passed).

**Pitch line (A5/A6):** "On today's levels, a player who never touches the new mechanic still scores >= 0.8 on about
a quarter to a third of rule uses (one-way tiles: 91% of their teaching levels). With the forcing generator: 0% of
teaching levels; avoiding the new rule costs at least 2x the optimal moves or makes the level unsolvable."
