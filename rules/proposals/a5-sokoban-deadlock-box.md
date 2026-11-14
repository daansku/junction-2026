# Rule Proposal: Irreversible Deadlock Corridor (`deadlock_reset` / corner-trap push block)

- **Origin:** A5 Research Digest (`docs/research/DIGEST.md`)
- **Target:** A1 (`engine/src/engine/components/` + generator constraint)
- **Tier:** Tier 2

## Visual Appearance (`64×64` frame)
- Uses existing `push_blocks` sprite (ring with centre dot) combined with a narrow corridor or recess where a block can be pushed *onto* a target/hole or *into* a corner against two walls.
- No extra visual clutter needed — once a block sits in a non-target wall corner, it visually cannot be pushed out.

## Mechanic
- In teaching and difficulty ≥ 2 levels with `push_blocks`, ensure at least one naive greedy path pushes the block into a corner/wall where it blocks the corridor or becomes unmovable, creating a soft-lock before the move budget hits zero.
- The optimal solution requires walking *around* the block first (a detour) to push from the opposite side, OR calling `RESET` promptly if the agent blunders into a deadlock.

## Why It Is Hard for Models (and Tests Reward Integrity)
1. **Tests lookahead & `RESET` judgment:** Frontier models frequently realize too late that a Sokoban box is stuck against a wall and burn 15–30 moves pushing against it (`repeated_no_effect_actions`) instead of calling `RESET` immediately.
2. **Separates `optimal` and `human` from naive policies:** Humans spot corner traps in 1–2 seconds; models often confuse "pushing failed" with "try another direction on the same box".
3. **Verifiable:** BFS checks that the level is solvable while at least one short greedy line leads to an unsolvable state.
