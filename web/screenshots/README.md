# Web app screenshots + screen recordings (A4-22)

1920×1080, dark theme, headless Chromium (Playwright) against the shared server's data (`?api=shared`), served from the
production build. Taken **Sat 14.11 ~18:30** (eval-v1 sweep in progress; eval-v2 runs in progress).
The challenge shots are real plays under the name `test`, a practice name the analysis drops.
Challenge stats come from `python web/scripts/challenge_stats.py --api <server> --game <game_id>`.

## Screenshots

| File | What |
|---|---|
| `01-overview.png` | `/` overview: recorded run playing, stats, top of the leaderboard |
| `02-gallery-eval-v1.png` / `02b-gallery-eval-v2.png` | gallery of the frozen eval collections |
| `03-game-detail.png` | `/gallery/gridworld-s900002-d3-l6-f09d6348`: rules per level, optimal path |
| `04-replay-argon.png` | Gemini 4 Argon winning eval-v1 game 1, step 42: reasoning, hypothesis, hidden truth, timeline |
| `05-compare-l2.png` | eval-v1 game 3 level 2 (hazards): daniel 11 moves vs Kimi K3.1 (h2, max) 32 vs Gemini 3.8 Flash 50 |
| `06-leaderboard.png` | leaderboard (A5) |
| `07-insights.png` | insights (A5) |
| `08-live.png` | live wall (runs in progress) |
| `09-kiosk.png` | `/kiosk`: the booth screen |
| `10-challenge-lobby.png` | `/challenge` lobby: game pick, recorded results, name, QR, visitor board |
| `11-challenge-playing.png` | mid level 1: no hints, "you are up against" |
| `12-challenge-level-solved.png` | level solved card + every model's recorded attempt on that level, replayed |
| `13-challenge-end.png` / `13b-challenge-end-full.png` | end screen: verdict, "Gemini 3.8 Flash needed 66 moves … you saw in 12", AI replays, table |
| `14-phone-challenge-lobby.png` / `15-phone-challenge-playing.png` | the same on a phone (390×844 @3x), touch d-pad |

## Screen recordings (`video/`, H.264 MP4, 1080p)

| File | Length | What |
|---|---|---|
| `challenge-full-run.mp4` | 57 s | lobby → 3 levels played → level-solved screens with AI replays → "You beat the AI" end screen |
| `replay-argon.mp4` | 31 s | Gemini 4 Argon replay playing from step 25 to its win, reasoning and hypotheses updating |
| `live-wall.mp4` | 23 s | live wall with the sweeps in progress |

The challenge recording is the optimal path at a steady pace (a scripted player, not a person): use it to show the
flow, not as a human result.
