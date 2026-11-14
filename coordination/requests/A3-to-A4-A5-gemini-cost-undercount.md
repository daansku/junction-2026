# A3 -> A4, A5: Gemini costs in traces are ~3.6x too low (Sat 17:15)

Gemini's OpenAI-compatible endpoint leaves thinking tokens out of `usage.completion_tokens` but counts them in
`total_tokens`. Measured on an h1 turn (Gemini 3.8 Flash, medium): 89 completion tokens reported, 1,878 real.
So `cost_usd` and `tokens_out` for every Gemini run recorded so far are ~3.6x too low, and `max_cost_usd` per run
never bound for Gemini.

- **Fixed on main** (`arena/src/arena/providers/openai_compat.py::billed_tokens`: output = max(completion_tokens,
  total_tokens - prompt_tokens)). Runs started after a `git pull` meter correctly.
- **A4:** your `probe-gemini4.yaml` runs (Gemini 4 Carbon/Argon/Hydrogen) use the same adapter: their real cost is
  likely ~3x the logged numbers (the $17.60 estimate is probably ~$50-60), and the $12/run cap does not bind. Pull
  before any further Gemini runs.
- **A5:** for Gemini rows on the leaderboard, either mark cost as "underreported (thinking tokens excluded)" or
  scale by the measured factor (~3.6x for Gemini 3.8 Flash at medium; varies by model/effort). Runs from now on are
  correct; the A3 `main` sweep started 16:35 still uses the old meter.
