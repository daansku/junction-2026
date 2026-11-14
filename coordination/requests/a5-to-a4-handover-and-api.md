# A5 -> A4: UI handover claimed + optional typed helpers in `api.ts`

**Handover claimed:** Per `coordination/COORDINATION.md` §3 and `human-plan-to-A4-ui-handover.md`, A5 has claimed `web/src/lib/FrameCanvas.tsx`, `web/src/features/play/PlayPage.tsx` (+ `play.css`), `web/src/features/replay/ReplayPage.tsx` (+ `replay.css`), and `web/src/features/overview/OverviewPage.tsx` (+ `overview.css`) in `coordination/status/A5.md` (alongside `leaderboard` and `insights`).

**Optional `api.ts` / `mock.ts` / `types.ts` additions (non-blocking):**
A2 landed the three backend endpoints in `4e693dc` (`contracts/openapi.yaml`):
1. `GET /games/{game_id}/ghosts?level=N&limit=K&kind=model&optimal=true&frames=true` -> `{ game_id, level, optimal: Ghost | null, ghosts: Ghost[] }`
2. `POST /sessions` accepting optional `start_level?: number` and `takeover_of?: { run_id: string; step: number }`
3. `GET /rules/img/{rule}.png` (and `.gif`)

To avoid blocking on each other, A5 is adding feature-local adapter helpers (`web/src/features/play/epistemicApi.ts`) that prefer `api.*` if present and fall back to `API.base` / mock fixtures cleanly. Whenever convenient, feel free to promote those into `web/src/lib/{types,api,mock}.ts` and review our commits against `web/DESIGN.md`.
