# A1 -> A3 (run), A7 (freeze): Kimi K3.1 Pro on eval-v3b under h2 (human request, Daniel, Sat ~22:15)

**Human request:** run Kimi K3.1 Pro on `eval-v3b` with the h2 harness. (Kimi is an API model: this is an evaluation run,
not training.)

**Before it starts (DECISIONS.md: no model runs on eval-v3b until Anssi says so):**
1. **Anssi** OKs model runs on eval-v3b and records it in DECISIONS.md.
2. **A7 freezes `data/collections/eval-v3b.json`** (`"frozen": true`, verify passes) and pushes, so results stay valid.
   The shared server already serves eval-v3b (`/api/games?collection=eval-v3b`, 30 games); A2 pulls once after the freeze.

**A3: sweep file to add as `arena/sweeps/h2-eval-v3b-kimi.yaml`** (you own `arena/sweeps/`; the key is only on your machine):
```yaml
# Human request Sat ~22:15 (Daniel): Kimi K3.1 Pro on all of eval-v3b, h2. Verda credits (no $ cost).
# Starts only after Anssi's OK + A7's freeze (DECISIONS.md). One attempt per game (labelled single-attempt).
name: h2-eval-v3b-kimi
harness: h2
collection: eval-v3b
games: all
attempts: 1
concurrency: 10
est_steps_per_game: 200
models:
  - {id: verda-kimi-k3-1-pro, effort: max}
budgets: {max_actions: 400, max_turns: 600, max_tokens_total: 500000000, max_cost_usd: 18.0, max_wall_s: 14400}
```
Run: `python -m arena sweep arena/sweeps/h2-eval-v3b-kimi.yaml --dry-run`, then without `--dry-run`.
Wall cap 4 h per run, so if started by 00:00 every run ends before the N3/N5 gates. Add `optimal`, `random`, `noop`
and `stop_early` baselines if the sweep does not already include them for eval-v3b (the board needs the reference rows).
Report in your timeline: games finished, levels, score with CI vs the eval-v2 h2 Kimi row (0.398, 0 of 4 won).

**Alternative if A3 is busy:** Ignacio sends Daniel `VERDA_INFERENCE_KEY` privately (never through git or chat logs);
Daniel puts it in `.env` on his machine and A1 runs the same file from there. Traces land on the shared server either way.
