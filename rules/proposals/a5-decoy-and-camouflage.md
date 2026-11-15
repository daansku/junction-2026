# Rule Proposal: Beacon-Linked Goal & Decoy Tile (`beacon_goal`)

- **Origin:** A5 Research Digest
- **Target:** A1 (`engine/src/engine/components/`)
- **Tier:** Tier 2 (or Tier 1 extension)

## Visual Appearance (`64×64` frame)
- Two (or three at `difficulty=3`) candidate ring-shaped goal tiles exist on the map, each in a distinct palette colour.
- A **beacon cell** (or HUD indicator strip) displays the exact colour of the *currently active* true goal.
- Stepping on a **decoy goal** does not win the level; instead it emits a `decoy_hit` penalty (costs 2 extra moves from the budget or teleports back to start) and rotates/flashes the beacon.

## Mechanic
- In standard gridworlds, even with `skin_shuffle`, once an agent touches a ring tile on Level 1 it learns "ring = goal".
- With `beacon_goal`, the player must visually match the beacon colour in the HUD/corner against the candidate goal tiles on the board before committing to a path.

## Why It Is Hard for Models (and Fair for Humans)
1. **Defeats heuristic nearest-goal bias:** Text-grid and multimodal LLMs often lock onto the closest ring tile without cross-referencing the beacon colour.
2. **100% visually observable:** A first-time human notices immediately that the beacon colour matches one of the ring tiles, satisfying AfterQuery's *Meaningful Difficulty* criterion (no hidden information).
3. **Trivial BFS integration:** Only the active goal cell terminates the level; decoy cells are modeled as penalty/reset hazards during BFS.
