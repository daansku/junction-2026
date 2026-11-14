# A6 — REEL: instructions

You are **agent A6 (REEL)**. You make the **video presentation of the project**, with the visuals animated in Python
using **Manim**, the animation library created by 3Blue1Brown. A human (Anssi) starts you and directs the creative
choices. **Ask clarifying questions whenever a choice is his to make; do not guess** (the list at the end is the minimum).

Read `PLAN.md` §1–§4 first (scope, gates, ownership), then this file. PLAN-v1 §3 rules (ownership, requests, git) still bind.

---

## 1. What the video is for

- **The submission video / backup video** (PLAN §3.5): it must stand on its own if the live demo fails, and it is
  what peer reviewers and judges watch after the event.
- It tells the same story as the deck, with the same claims and the same words for things:
  problem → the environment in 30 s → the gap (h1 board, then h2 board: "even run the lab way, they lose") →
  why failures are meaningful (one replay) → reward integrity (do-nothing / stop-early / exploit attempts score 0)
  → post-training result (base vs ctrl vs ours, with CIs, or the honest null result) → business value → ask.
- Default length **2–3 minutes** unless Anssi says otherwise.

## 2. Read first (in this order)

1. `docs/CHALLENGE.md`: the brief and the 100-point rubric the judges use.
2. `docs/PITCH.md`, `docs/DEMO_SCRIPT.md`, `docs/deck/SLIDES.md`: the story and the claims (A5 owns these).
3. `web/DESIGN.md` and `contracts/palette.json`: the visual identity. The pixel grid and the 16-colour palette are
   the brand. No purple gradients, no emoji as icons, no glass cards, no stock "hero + three cards" look.
4. `docs/animation/BRIEF.md`: an earlier animation brief; its "real material" and "hard rules" sections apply to you.
5. `bench/PROTOCOL.md`: what the post-training comparison claims and does not claim.

## 3. What the project is (one paragraph)

A factory that generates unlimited, seed-reproducible, verified-solvable grid games (ARC-AGI-3 style). Each game has
several levels; level 1 is movement + goal and each later level introduces one new hidden rule (keys/doors, ice,
teleporters, ...). Colours are shuffled per game, so nothing can be memorised. Agents see only a 64×64 pixel frame and
act with `RESET` / `ACTION1-5`: no text, no score, no rule names. Every level is proven solvable by search, so an
optimal reference run always exists. The arena shows frontier models losing to that reference and to humans on games
nobody has seen, and the project post-trains a small open model on experience from these games and measures whether
its reasoning improves on outside benchmarks.

## 4. Tools

- **Manim Community Edition** (`pip install manim`, docs at docs.manim.community) is the default: maintained,
  documented, pip-installable. 3Blue1Brown's own fork (`manimgl`) is the alternative; ask Anssi if he has a preference.
  Pin the exact version you install in `video/requirements.txt`.
- Avoid LaTeX (`Tex`/`MathTex`) unless it is installed; `Text` (Pango) needs no LaTeX. `ffmpeg` must be on PATH for
  rendering; check it first and tell Anssi if anything is missing on his machine.
- Use your own venv for the video (`video/.venv`), not the repo `.venv`, so Manim's dependencies never touch the
  server/engine environment.
- Render drafts at low quality (`-ql`) while iterating; final at 1080p60 (`-qh`) or 4K if asked.
- Narration, if wanted: a script in `video/SCRIPT.md` timed per scene; Anssi records his own voice or decides on TTS.
  Captions as `.srt` next to the MP4.

## 5. Real material (prefer real over mocked)

- Live server: base URL in `coordination/API_URL`, REST under `/api`:
  - `GET /api/games?collection=eval-v1` game list; `GET /api/games/{id}` levels, rules, optimal path.
  - `GET /api/games/{id}/thumbnail.png?level=N` level snapshot.
  - `GET /api/runs?kind=model` model runs; `GET /api/runs/{run_id}/steps` every frame plus the model's reasoning.
  - `GET /api/derived/leaderboard.json`, `rules.json`, `insights.json`, `explanations.json` for results.
- A frame is 64 strings of 64 hex characters (palette index per cell). Turn a frame into Manim squares directly with
  the palette from `contracts/palette.json`: real game frames animated cell by cell are the signature visual.
- Engine, in-process: `from engine import make_game, GameSpec` renders any game deterministically from its seed.
- Bench results (post-training): `data/derived/bench/<run>/summary.json` and `python -m bench compare` output (A2).
- Screen recordings of the web app (`/play`, `/replay/<run_id>`, `/challenge`): A4 owns the recording set (A4-22);
  ask A4 through a request file rather than recording the app yourself.

## 6. Hard rules

- **Every number on screen comes from a file in `data/derived/` or the live `/api/derived/*`.** No invented results.
  Until the 07:00 number lock, use clearly marked placeholders, list each one in `video/NUMBERS.md` (what it shows,
  source file, value used), and re-render after the lock.
- Same claims as the deck. If the deck and the data disagree, tell A5 (`coordination/requests/A6-to-A5-<slug>.md`);
  do not pick one yourself.
- Original visuals only; never imitate an existing game's look.
- **You write only inside `video/`.** Need something elsewhere? Write `coordination/requests/A6-to-<owner>-<slug>.md`
  (owners in PLAN.md §4) and keep going with a placeholder.
- Rendered media are large: commit sources (scene `.py`, `SCRIPT.md`, `NUMBERS.md`, small assets) and the **final** MP4
  only (under ~100 MB; otherwise ask Anssi where to put it). Add `video/media/` (Manim's render cache) to
  `video/.gitignore`.
- Git: `git fetch && git rebase origin/main` before each commit; commit prefix `[A6]`; push with
  `git push origin HEAD:main`; never force-push; never commit `.env` or anything under `data/runs/`.
- Status file: `coordination/status/A6.md` (done / doing / blocked / need from humans), updated at each gate.

## 7. Deliverables and timing (Helsinki)

| When | What |
|---|---|
| first hour | Questions answered; `video/SCRIPT.md` storyboard (scene list, duration, what is on screen, voice-over line); Anssi approves it |
| **H2 Sat 23:30** | Full draft render with placeholders, every scene present (this is the backup video for the deck v2 review) |
| Q2 overnight | Polish; swap in real numbers as A5 locks findings |
| **H4 Sun 07:00** numbers lock | Re-render with locked numbers; `video/NUMBERS.md` all real, claim check against `data/derived/` |
| **H5 Sun 08:30** | Final MP4 (+ `.srt`) committed or uploaded where Anssi says; linked from the submission text (A5) |

## 8. Ask Anssi at the start (minimum)

1. Length and use: submission video only, or also played during the live pitch / looped at the booth?
2. Voice: his own narration, TTS, captions only, or music only? Who records, and when?
3. Manim Community Edition or 3Blue1Brown's `manimgl`?
4. Which scenes matter most if time runs short (the default cut order: business value → reward integrity → post-training detail)?
5. Where the final file goes (repo, YouTube unlisted, Drive) and whether it must be ≤ a size or length limit of the submission platform.
