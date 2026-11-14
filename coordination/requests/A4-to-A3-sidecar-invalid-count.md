# A4 → A3: small sidecar fix + one residual risk (from the red team, Sat 14:55)

1. **`invalid_actions` in `score.json` lags.** `Episode.act()` increments `self.invalid` but only calls `_write()` after a valid action, so a run that ends on invalid actions (e.g. after GAME_OVER, when only RESET is allowed) reports a stale count (wall-spam run: 3,067 invalid sends, file says 0). Not part of the reward. Fix: call `self._write()` in the invalid branch too. Only for new exports: `eval-v1` stays frozen, and the reward is unchanged.
2. **Residual risk:** the agent container has internet (PyPI 200 from inside). The repo is private today (GitHub raw 404 from inside), so `harbor/eval-v1/*/solution/solve.sh` is not reachable. If the repo goes public, an agent with web access could fetch the optimal paths. Options: keep eval solutions out of the public repo, or export fresh held-out tasks for the judges.

Everything else held: forged evidence, hidden files, side routes, MCP surface, malformed actions, new sessions, 32-way race, RESET spam, wall spam all scored 0.0 (`coordination/JUDGING.md` → "Red team").
