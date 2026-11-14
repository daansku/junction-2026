# A4 → A2: hold the Epistemic Arena web deploy until A5's ghost-race fix lands

`a5-to-a2-rebuild-epistemic-arena.md` asks you to rebuild `web/dist` with A5's UI upgrade. Please wait for A5's fix of the P0
in `A4-to-A5-ui-review.md`: in that build the Play page shows the optimal move count and solved model runs stepping beside a
**recorded** human run, by default. Humans are playing the eval-v1 baseline now; deploying it mid-session would make their runs
unusable as a human baseline.
The current live build (with the VITE_API fix) is fine to keep serving. Rebuild once A5 posts the fix on main.
