# Presentation animation: brief for the agent

You are making the animation that presents this project (Junction 2026, AfterQuery RL-environment challenge).
A human (Anssi) directs the work in this session. Ask before big creative choices; do not guess.

## Read first (in this order)
1. `docs/CHALLENGE.md`: the brief and the 100-point rubric the judges use.
2. `docs/PITCH.md` and `docs/DEMO_SCRIPT.md`: the story and the 10-minute demo the animation supports.
3. `docs/deck/SLIDES.md`: the deck it must match (same claims, same words for things).
4. `web/DESIGN.md`: visual identity. The pixel grid and the 16-colour palette (`contracts/palette.json`) are the brand.
   No purple gradients, no emoji as icons, no glass cards, no "hero + three feature cards".
5. Load the `frontend-design` skill before designing anything.

## What the project is (one paragraph)
A factory that generates unlimited, seed-reproducible, verified-solvable grid games (ARC-AGI-3 style). Each game has
6 levels; level 1 is movement + goal, each later level introduces one new hidden rule (keys/doors, ice, teleporters...),
colours are shuffled per game so nothing can be memorised. Agents see only a 64x64 pixel frame and act with
`RESET` / `ACTION1-5`; no text, no score, no rule names. Every level is proven solvable by BFS, so an optimal reference
run always exists. The arena shows frontier models losing to that reference (and to humans) on games nobody has seen.

## Real material you can use (prefer real over mocked)
- Live server: URL in `coordination/API_URL` (plain HTTP API, base `/api`):
  - `GET /api/games?collection=dev` game list; `GET /api/games/{id}` levels, rules, optimal path.
  - `GET /api/games/{id}/thumbnail.png?level=N` level snapshot.
  - `GET /api/runs?kind=model` model runs; `GET /api/runs/{run_id}/steps` every frame plus the model's reasoning.
  - `GET /api/derived/leaderboard.json`, `rules.json`, `insights.json` for the results.
- Frames are 64 strings of 64 hex chars (palette index per cell). `server/src/server/render.py` turns one into a PNG.
- Engine CLI for renders and contact sheets: `python -m engine --help` (run inside the repo venv, `.venv`).
- The web app (`<API_URL>/play`, `/replay/<run_id>`) can be screen-recorded.

## Hard rules
- Every number shown must come from a file in `data/derived/` or the live `/api/derived/*`. No invented results.
  If the final numbers are not in yet, use clearly marked placeholders and list them in this folder's `NUMBERS.md`.
- Original visuals only; do not imitate any existing game's look.
- Work only inside `docs/animation/`. `docs/` belongs to agent A5 (LENS), which writes the deck; do not edit its files.
  Need a deck change? Write `coordination/requests/anim-to-A5-<slug>.md`.
- Git: `git fetch && git rebase origin/main` before each commit; commit prefix `[ANIM]`; push with
  `git push origin HEAD:main`. Never force-push. Never commit `.env` or anything under `data/runs/`.

## Ask Anssi at the start
1. Length, and where it plays: opening of the live pitch, the submission video, or a loop on a screen?
2. Output format: video file (MP4), an HTML/JS animation run in the browser, or both?
3. Narrated, captioned, or silent with music?
4. Deadline. The final submission is Sun 15.11 at 10:00 and the team submits at 09:30; the demo video is due by Sat ~23:30.
