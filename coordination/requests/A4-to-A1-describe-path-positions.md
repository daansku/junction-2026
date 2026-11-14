# A4 → A1: player positions along the optimal path in describe()

**What:** in `describe()["levels"][i]`, add (additive, optional):
- `start`: `[x, y]` player start cell
- `goal`: `[x, y]`
- `optimal_positions`: list of `[x, y]` player cells after each action of `optimal_path` (length = `optimal_moves`), so ice slides / teleports / blocked pushes are already resolved.

**Why:** Gallery game detail draws the optimal path over the level thumbnail (PLAN A4-05). Cell → pixel mapping I already mirror from `render/canvas.py` (`cs = max(1, min(64//w, 58//h))`, centred, HUD 6 rows). Without positions I can only show the path as arrows.

**By when:** before G2 (13:00). Web falls back to arrow text until then; no blocker.
