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

## Branching generator `gridbranch` (Sat ~20:30, BRANCH_VERSION 1), human request: "more alternative paths"

`engine/src/engine/generator/branching.py`; `gridforce` is untouched so the two can be compared. Topology metrics
(walls only, rule objects ignored): **real loops** = independent cycles around wall clusters (planar faces of the
floor graph that are not open 2x2 squares, so open floor does not count); **linear level** = under 20% of the
optimal route's cells have a bypass (are not cut points of the floor graph).

| Collection (30 games, d1-d3, 6 levels) | Real loops / level | Linear levels | Optimal moves / level | New rule forced | Use-rule avoider >= 0.8 |
|---|---:|---:|---:|---:|---:|
| eval-v1 (`gridworld`) | 1.1 | 10% | 15.5 | 73/111 | 28% |
| eval-v3 (`gridforce`) | 1.2 | 13% | 16.9 | 112/112 | 4% |
| **eval-v3b (`gridbranch`)** | **4.0** | **0%** | **29.1** | **106/106** | 7% |

Fresh gridbranch samples (12 games each): d1 3.1 loops / 26 moves, d2 4.1 / 30, d3 5.0 / 31, d4 (8 levels) 6.3 / 45;
median 1.2-3.8 s per game, worst ~40 s (d4). Targets ramp per level: loops >= min(6, 1 + level/2 + (d-1)),
bypass >= 0.30 + 0.05 x level + 0.05 x (d-1); relaxed one step after 40 attempts.

### gridbranch v2 (BRANCH_VERSION 2, Sat ~21:30): fewer rejections, mechanics on every route

Profile, 30 games d1-d3 x 6 levels (`branching.REJECTS` / `SECONDS` diagnostics):

| | Candidates | Accepted | Time |
|---|---:|---:|---:|
| v1 | 13,497 | 1.3% | 102 s |
| v2 | 3,247 | 5.5% | 82 s |

v2 changes: loops are built (walls joining distant corridors opened until the target is met, vault cells
kept) instead of rejected; start/goal are a far pair (double sweep); a goal vault is always built when a gate
rule needs a chokepoint, shifted to fit at map edges, entrance facing away from the start, with a walled
corridor of one extra chokepoint per gate; a teleport-aware draft so A1's placement still finds routes
after teleporters wall the goal side off; one_way / hazards / push_blocks / ice placed on a max-flow minimum
cut across every start-goal route (naive shortest route = the trap: arrow against travel, lethal hazard run;
other routes passable or survivable); cheapest checks first.

eval-v3b rebuilt with v2 (same seeds and shape): 3.4 real loops/level, 0% linear, 25.9 optimal moves, new
rule forced 108/108, use-rule avoider >= 0.8 on 3% (v1: 7%). Route rules forced, v1 vs v2: one_way 14/19 vs
21/23, push_blocks 13/16 vs 19/22, ice 29/32 vs 35/36, hazards 23/23 vs 27/27. 0 failures at d1-d4.
