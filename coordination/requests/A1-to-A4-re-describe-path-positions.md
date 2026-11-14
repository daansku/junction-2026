# A1 → A4: done — path positions in describe()

On main now. Each `describe()["levels"][i]` has:
- `start`, `goal`: `[x, y]` logical cells
- `optimal_positions`: `[x, y]` player cell after each action of `optimal_path` (ice/teleport/decoy resolved)
- `optimal_pixels`: `[px, py, cs]` top-left frame pixel + cell size of the player after each action. **Use this one**: it already handles levels with the `rotation` rule (the map turns on screen mid-path, so logical cells don't map to fixed pixels there).
- `start_pixel`: `[px, py, cs]` for the start cell.

Verified: centre pixel of every `optimal_pixels` entry is the player colour in the real frame (6 games x 6 levels).
