# Game Factory pitch: deck v3 (speaker notes and sources)

Open `docs/deck/index.html` in a browser (or the published copy). Arrow keys or Space move between slides;
**P** starts Present mode (one slide, full screen; click the right two thirds to go forward). Esc leaves it.
Built by A1 at the humans' request (Sat ~20:15), replacing deck v2. Numbers are from boards rebuilt at 17:49 UTC
from the shared server's export (652 runs); rebuild and update the marked figures after the 07:00 lock.

Timing target: 10 minutes including the live demo. Rewrite the notes in your own words.

| # | Slide | Say (about) | Time |
|---|---|---|---|
| 1 | **Game Factory**: unlimited games no model has seen; frontier agents finish easy ones; on new rules humans win. Hero = a real eval-v2 frame. | "This is exactly what the model sees: 64 by 64 cells, 16 colours, no words." | 0:30 |
| 2 | **The problem**: a benchmark that ends up in training data measures memory. | Leakage; agents meet rules without a manual; we need unseen tests with provable answers. | 0:45 |
| 3 | **The environment**: 21 rules, 2,035 training games, 60 frozen test games; every level checked (search, every rule matters, random <2%). GIFs = real teaching levels. | Point at one GIF (ice or teleporters) and say what the player has to discover. | 1:00 |
| 4 | **Live demo** `/challenge` + QR. | Hand a phone to a judge or play one level live; show the AI replays appear. Fallback: `web/screenshots/video/challenge-full-run.mp4` (scripted optimal player, say so). | 2:00 |
| 5 | **The gap (h1, eval-v2), ranked completion first**: optimal 100% · humans 73% won (16 of 22, eff 0.67) · Gemini 4 Carbon 60% (6 of 10, eff 0.74) · Argon 14% (3 of 22) · Kimi K3.1 0 of 3 · Gemini Flash 0 of 19 · random / do nothing 0. | Headline sentence. Say the ranking rule (games won, then levels, then efficiency) and that it was set after the results were in. | 1:00 |
| 6 | **Run the lab way**: same 4 eval-v2 games. h2: Gemini Pro and Kimi 0 of 4. h2b (up to 5 moves per call): Gemini 4 Argon 8 of 8, Carbon 12 of 12, Flash 7 of 9; humans 5 of 6. | Be straight: the newest models catch up with the right harness. Bridge: "most models still fail, and here is why" (slide 7). | 1:00 |
| 7 | **Why they fail**: 50% repeating moves that change nothing, 44% not restarting a doomed level (194 failure points). | Show one replay if time allows (`/replay`). | 0:45 |
| 8 | **Reward integrity**: Harbor reference 1.000, do nothing 0.000, stop-early 0.167 / 0.500, OpenCode + Nemotron 0.067; 9 of 9 container attacks 0.0. | "Judges: the only way to score is to play well. Try us." | 0:45 |
| 9 | **Post-training**: SFT v1 4 of 180 levels; SFT v2 three-way + RL (incl. game_turn on the maps); outside benchmarks with pre-registered rule. **Result box is a placeholder until 07:00.** | Replace the dashed box with base / ctrl / ours and CIs. If no transfer, say so (honesty rule). | 1:00 |
| 10 | **Business**: contamination-proof evals · pre-deployment agent checks · verified training data and levels. | If transfer failed: "that is evidence you can't train to our test." | 0:45 |
| 11 | **Try to break it**: Harbor commands, live pages. | Ask + invite the 15-minute exploit hunt. | 0:30 |

## Sources for every figure

| Figure | Source |
|---|---|
| 21 rules, engine 0.6.0, 1,000/1,000 fuzz | `engine/src/engine/components/`, `rules/CATALOG.md`, A1 status |
| 2,035 training games; 30 + 30 frozen test games | `data/collections/train-v1.json`, `eval-v1.json`, `eval-v2.json` |
| Slide 5 bars | `leaderboard.json` (h1) built Sun 00:00 by `analysis.cli.build_all` from the 1,281-run export, finished attempts only, completion-first ranking |
| Slide 6 bars | `leaderboard_h2.json` and `leaderboard_h2b.json`, same build |
| 50% / 44% / 194 failure points | `decision_points.json`, same build |
| Harbor rows, red team | `coordination/JUDGING.md` (Results, Red team) |
| SFT v1 4/180 levels | `coordination/status/A3.md` (A3-20 finetune-eval, 30 games) |
| Post-training protocol | `bench/PROTOCOL.md` v3 (human sign-off), `FT_BENCHMARKS.md` |

## To update after the 07:00 lock
1. Rebuild the boards (`python -m analysis build`, or `analysis.cli.build_all` on Python 3.14, where the CLI's argparse
   help string fails) and replace the figures on slides 5, 6 and 7 if they moved.
2. Fill slide 9's result box from `bench_summary.json`.
3. A4 retakes `web/screenshots/` (`python web/scripts/deck_capture.py`); copy `12-challenge-level-solved.png` and
   `04-replay-argon.png` over `docs/deck/assets/challenge.png` and `replay.png`.
