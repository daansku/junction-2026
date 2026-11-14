# A4 → A5: handover of Play, Replay, Overview and FrameCanvas (UI upgrade)

Human decision Sat 14:10 (`DECISIONS.md`, `COORDINATION.md` §3): A5 leads the "Epistemic Arena" UI upgrade.
A4 has **no unfinished change** in these files; everything is on `main` as of `2a8718c` (Sat 14:30).
**Claim them in `coordination/status/A5.md`; from then on A4 stops editing them.**

## Files that move to A5
| File | Notes |
|---|---|
| `web/src/lib/FrameCanvas.tsx` | **Shared:** also used by Gallery (`GalleryPage`, `GameDetail`), Compare and the Live wall, which stay A4's. Keep the current props working (`frame`, `scale` number or `'fit'`, `minScale`, `maxScale`, `viewportReserve`, `grid`, `overlay`, `className`, `label`); add new ones as optional. |
| `web/src/features/play/PlayPage.tsx` | |
| `web/src/features/play/NewGamePanel.tsx` | Not named in the plan, but only Play uses it: take it with Play. |
| `web/src/features/play/play.css` | Goes with Play. |
| `web/src/features/replay/ReplayPage.tsx` | Also exports `ReplayIndexPage` (`/replay`, the run list), imported by `app/App.tsx`. Keep both exports or tell A4 to change the router. |
| `web/src/features/replay/replay.css` | Goes with Replay. `live.css` and `LiveWall.tsx` stay A4's. |
| `web/src/features/overview/OverviewPage.tsx`, `overview.css` | |

## Behaviour that must survive the redesign (each one fixed a real problem today)
**Play**
- **Name required on the shared server** (`nameRequired`: same-origin / shared / custom API, not published mode). Humans were playing as `anonymous`, useless for the baseline. Practice name `test`; analysis drops `anonymous` / `test`.
- **One move at a time:** key presses while a move is in flight, or within `MOVE_COOLDOWN_MS` (120 ms), are dropped, not queued. Queued presses replayed spammed moves late on a laggy tunnel (playtest feedback). Truth is fetched after each move without blocking the next one.
- **First attempt only:** games already played under your name are marked "· played" in the picker, with a warning and a "next game you haven't played" link. The human baseline counts first attempts.
- **Runs are closed:** `endSession` on win, game switch, restart and `pagehide` (keepalive), so the shared server has no dangling sessions.
- **New game:** `POST /api/games/generate` (A2, live), then the run starts on its own; messages for 403 (eval seeds), 422, 429 (30 per minute per visitor), 503. Seed + copy link in the "this game" panel.
- The truth overlay is a playtester debug toggle, off by default. The player sees only the frame.
- Touch d-pad for phones; the frame fits the viewport height at 1080p (`viewportReserve`).
- Published mode: no replay link for the visitor's own run (visitor runs are not in `/runs` there).

**Replay**
- `?step=N` deep links (Insights links to `/replay/<run>?step=<n>`); live follow for `IN_PROGRESS` runs (polls), stops following when the viewer scrubs.
- Keyboard: ←/→ step, Shift ×10, Space play, `[` `]` speed.
- Belief vs real state check, per-step usage and latency, level timeline with new-rule labels, reset and game-over marks.

**Overview**
- Shows an error with Retry when the server is unreachable (it used to show blank stats). Hides the Live link in published mode.

## Things outside these files you can rely on (A4 keeps them)
- `lib/api.ts`: `generateGame()` is there; ask A4 for the A2 endpoints when they land (`GET /api/games/{id}/ghosts`, `start_level` / `takeover_of` on `POST /sessions`, `GET /api/rules/img/{rule}.png`). A4 adds the client methods and mock versions on request.
- `lib/config.ts`: API selection, now ignores invalid `VITE_API` values (the live build had `C:/Program Files/Git/api`).
- `design/primitives.tsx` + `tokens.css`: tell A4 which shared pieces you need (bezel, ruler, pill, split divider…); A4 adds them so Gallery / Compare / Live can use them too.
- `web/DESIGN.md`: A4 reviews your pages against it as they land on `main`.

## Testing without polluting results
- Mock mode (`?api=mock`) needs no server; `?api=local` with a local server for real games.
- On the shared server use player name `test`. Never start model or baseline sessions from the browser.
- Screenshots for the deck: `web/screenshots/README.md` has the headless command.
