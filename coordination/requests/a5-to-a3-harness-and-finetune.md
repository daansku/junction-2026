# Request: A5 (LENS) -> A3 (ARENA) — Harness Telemetry & Fine-Tuning Data Recipe

**By when:** Before `h1` harness freeze (`12:00` Sat) and `train-v1` dataset build (`A3-09`).

## What A5 Needs / Recommends (from Research Digest `docs/research/DIGEST.md`)

1. **Keep `hypothesis` and `belief` Cleanly Populated (and Test Prompt Strictness):**
   - `analysis` (`rules.json` and `insights.json`) parses `step.hypothesis`, `step.reasoning`, and `step.belief` directly from `steps.jsonl`.
   - In `system_h1.md`, models already output `{notes, hypothesis, belief, action}` and `agent_loop.py` maps `reasoning=parsed["notes"]`. Please ensure `belief` is preserved as `"playing" | "won" | "lost"` without overwriting it to `"playing"` if the model outputs `"won"` or `"lost"` (checked `agent_loop.py:74` — already solid!).
   - Keep `player.effort`, `player.model_id`, `player.provider`, and `player.input_modes` in `POST /sessions` so `leaderboard.json` can cleanly slice effort ablations (`low` / `medium` / `high`) and input-mode comparisons (`image` vs `text` vs `image+text`).

2. **Always Include `noop` and `stop_early` in Eval Sweeps:**
   - Per `docs/CHALLENGE.md`, AfterQuery judges explicitly check `noop` (do-nothing) and `stop_early` baselines for reward hacking.
   - Keep `noop` and `stop_early` in `arena/sweeps/` (already in `baselines.py`!) so `leaderboard.json` automatically displays their `0.000` score on the public dashboard as live proof of reward integrity.

3. **Perception / Cell-Diff Summary (Fairness Rule):**
   - Remember PLAN.md §A3-09: if you add any agent-side perception helper (such as your RLE encoding or a diff-bounding-box summary), apply it uniformly to **all** evaluated models under the same harness version (`h1` vs `h2`) and never mix harness versions in a single leaderboard ranking without marking `harness_version`.

4. **Fine-Tuning Dataset Recipe (`A3-09`) for the Tiebreaker:**
   - Mix **~70% optimal BFS trajectories** (clean shortest-path play with synthetic rule-discovery `notes`/`hypothesis` that do NOT leak hidden truth names) with **~30% mistake-recovery trajectories**:
     - intentional wall bump -> note obstacle + avoid repeating;
     - intentional hazard step or wrong one-way attempt -> update hypothesis;
     - intentional deadlock / budget exhaustion -> issue `RESET` early rather than burning remaining budget;
     - intentional skin-shuffle variation across `train-v1` seeds (keeping eval skins/rule pairs strictly disjoint).
   - This directly targets the two largest failure modes we expect in frontier traces: `repeated_no_effect_actions` and late `RESET` decisions.
