# Rule Proposal: Delayed / Toggling State Switch (`toggle_walls` / delayed gate)

- **Origin:** A5 Research Digest (`docs/research/DIGEST.md`)
- **Target:** A1 (`engine/src/engine/components/`)
- **Tier:** Tier 2

## Visual Appearance (`64×64` frame)
- **Toggling walls / gates:** Rendered with the component's skinned colour using a distinct hollow-frame or dotted pattern when open (passable) and solid checkerboard/bar pattern when closed (impassable), plus a small 1px phase pip in the top HUD bar (`rows 3–4`) showing remaining moves until the next toggle.

## Mechanic
- **Either** walls/gates flip state (`open <-> closed`) deterministically every `k` moves (`k ∈ {2, 3, 4}` depending on difficulty), **or** stepping on a delayed switch opens a distant gate after `k` steps for a window of `m` steps.
- Every action increments the step counter; bumping into a closed toggling wall still advances the counter (observable via HUD phase pip change).

## Why It Is Hard for Models (and Easy to Verify)
1. **Breaks static path planners:** Models that infer a wall map once at `t=0` fail to notice periodic state changes unless they correlate the HUD phase pip with tile transitions.
2. **Tests temporal credit assignment:** Unlike `keys_doors` (permanent state change) or `plates_gates` (immediate toggle on plate), delayed/periodic switches require multi-step lookahead in state-time space `(x, y, t mod k)`.
3. **Solver compatibility:** BFS over `(pos, t % k, ...)` remains exact and small (`k <= 4` multiplies state space by at most `4×`). Rule-necessity check verifies the optimal path cannot ignore the phase timing.
