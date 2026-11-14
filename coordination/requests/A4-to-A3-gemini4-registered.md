# A4 → A3: Gemini 4 models added to `arena/models.yaml` + a 1-game probe running (human request, Sat 16:45)

Our `GEMINI_API_KEY` sees `gemini-4-carbon`, `gemini-4-argon`, `gemini-4-hydrogen` (live `/models`, 2026-11-14). A4 added three
registry rows (after `gemini-pro`), with prices from aistudio.google.com/docs/pricing (standard paid tier, output incl. thinking):
Carbon and Argon $2.00 / $10.00 per 1M tokens (doubling on 2026-12-01), Hydrogen $1.50 / $7.50. Text + image and
`reasoning_effort` verified through `OpenAICompatProvider`.

Running from A4's machine on the Verda host: `arena/sweeps/probe-gemini4.yaml`, eval-v1 game 1 (s900000 d1, the game Opus
also played) × 1 per model, effort medium, h1, max 400 actions, cost cap $12 per run. Dry-run $17.60 (human approved).
A4 reports actions, levels and real cost per action when they finish; a bigger subset is the human's call after that.

No change to your files beyond the three new rows.
