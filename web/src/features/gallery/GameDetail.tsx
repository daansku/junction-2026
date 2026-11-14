import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { MockApi } from '@/lib/mock'
import type { GameDescribe, LevelDescribe, RunMeta } from '@/lib/types'
import { Button, Chip, Empty, ErrorState, Loading, PageHeader, Panel } from '@/design/primitives'

const ARROW: Record<string, string> = { ACTION1: '↑', ACTION2: '↓', ACTION3: '←', ACTION4: '→', ACTION5: '␣', RESET: 'R' }

// Mirrors engine/src/engine/render/canvas.py: HUD 6 rows, integer cell size, centred.
const HUD_ROWS = 6
function cellGeometry(w: number, h: number) {
  const cs = Math.max(1, Math.min(Math.floor(64 / w), Math.floor((64 - HUD_ROWS) / h)))
  return { cs, ox: Math.floor((64 - w * cs) / 2), oy: HUD_ROWS + Math.floor((64 - HUD_ROWS - h * cs) / 2) }
}

/** Optimal path drawn over a level thumbnail. Needs start + optimal_positions from describe(). */
function PathOverlay({ level }: { level: LevelDescribe }) {
  if (!level.w || !level.h || !level.start || !level.optimal_positions?.length) return null
  const { cs, ox, oy } = cellGeometry(level.w, level.h)
  const pts = [level.start, ...level.optimal_positions].map(([x, y]) => `${ox + (x + 0.5) * cs},${oy + (y + 0.5) * cs}`)
  return (
    <svg viewBox="0 0 64 64" width="100%" height="100%" aria-hidden>
      <polyline
        points={pts.join(' ')}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={Math.max(0.5, cs / 5)}
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity={0.9}
      />
    </svg>
  )
}

function LevelThumb({ game, level, showPath }: { game: GameDescribe; level: LevelDescribe; showPath: boolean }) {
  const base = api.thumbnailUrl({ ...game, thumbnail_url: game.thumbnail_url ?? `/games/${game.game_id}/thumbnail.png` })
  const overlay = showPath ? <PathOverlay level={level} /> : null
  if (base && !(api instanceof MockApi)) {
    const sep = base.includes('?') ? '&' : '?'
    return (
      <div className="level-thumb">
        <img src={`${base}${sep}level=${level.level}`} alt={`Level ${level.level}`} width={256} height={256} loading="lazy" />
        {overlay && <div className="level-thumb-overlay">{overlay}</div>}
      </div>
    )
  }
  const frame = api instanceof MockApi ? api.previewFrame(game.game_id) : null
  return <FrameCanvas frame={frame} scale={4} overlay={overlay} />
}

function bestByPlayer(runs: RunMeta[]) {
  const best = new Map<string, RunMeta & { attempts: number }>()
  for (const r of runs) {
    const key = `${r.player?.kind}:${r.player?.model_id ?? r.player?.name}:${r.player?.effort ?? ''}`
    const prev = best.get(key)
    const better =
      !prev ||
      (r.levels_completed ?? 0) > (prev.levels_completed ?? 0) ||
      ((r.levels_completed ?? 0) === (prev.levels_completed ?? 0) && (r.actions ?? 1e9) < (prev.actions ?? 1e9))
    best.set(key, { ...(better ? r : prev!), attempts: (prev?.attempts ?? 0) + 1 })
  }
  return [...best.values()].sort(
    (a, b) => (b.levels_completed ?? 0) - (a.levels_completed ?? 0) || (a.actions ?? 0) - (b.actions ?? 0),
  )
}

export function GameDetail({ gameId }: { gameId: string }) {
  const game = useQuery({ queryKey: ['game', gameId], queryFn: () => api.getGame(gameId) })
  const runs = useQuery({ queryKey: ['runs', gameId, undefined], queryFn: () => api.listRuns({ game_id: gameId }) })
  const [showPath, setShowPath] = useState(true)

  if (game.isLoading) return <Loading what="Loading game" />
  if (game.error) return <ErrorState error={game.error} retry={() => game.refetch()} />
  const g = game.data!
  const hasPositions = g.levels.some((l) => l.optimal_positions?.length)
  const totalOpt = g.optimal_moves_total ?? g.levels.reduce((s, l) => s + (l.optimal_moves ?? 0), 0)
  const totalBudget = g.levels.reduce((s, l) => s + (l.move_budget ?? 0), 0)

  return (
    <>
      <PageHeader
        title={<span className="mono">{g.game_id}</span>}
        sub={
          <span className="mono">
            {g.collection ?? g.spec?.family ?? ''} · seed {g.spec?.seed ?? g.seed} · difficulty{' '}
            {g.difficulty ?? g.spec?.difficulty} · {g.levels.length} levels · optimal {totalOpt} · budget {totalBudget}
            {g.engine_version ? ` · engine ${g.engine_version}` : ''}
          </span>
        }
        actions={
          <>
            <Link to="/gallery" className="muted">
              all games
            </Link>
            {hasPositions && (
              <Button mono active={showPath} onClick={() => setShowPath((v) => !v)}>
                optimal path
              </Button>
            )}
            <Link to={`/compare?game=${encodeURIComponent(g.game_id)}`}>Compare runs</Link>
            <Link to={`/play/${encodeURIComponent(g.game_id)}`}>
              <Button variant="primary">Play this game</Button>
            </Link>
          </>
        }
      />

      <div className="levels-grid">
        {g.levels.map((l) => (
          <Panel
            key={l.level}
            label={
              <Link to={`/compare?game=${encodeURIComponent(g.game_id)}&level=${l.level}`} title="Compare runs on this level">
                level {l.level}
              </Link>
            }
            actions={l.new_rule ? <span className="new-rule mono">+ {l.new_rule}</span> : null}
            className="level-card"
          >
            <LevelThumb game={g} level={l} showPath={showPath} />
            <dl className="level-facts mono">
              <dt>rules</dt>
              <dd>{l.rules.length ? l.rules.join(', ') : 'walls, goal'}</dd>
              <dt>optimal</dt>
              <dd>
                {l.optimal_moves} moves · budget {l.move_budget}
                <span className="muted"> ({(l.move_budget / Math.max(1, l.optimal_moves)).toFixed(1)}×)</span>
              </dd>
              {(l.w || l.layout) && (
                <>
                  <dt>layout</dt>
                  <dd>
                    {l.layout ?? '—'}
                    {l.w ? ` · ${l.w}×${l.h}` : ''}
                  </dd>
                </>
              )}
              {l.optimal_path && (
                <>
                  <dt>path</dt>
                  <dd className="path-arrows">{l.optimal_path.map((a) => ARROW[a] ?? a).join('')}</dd>
                </>
              )}
            </dl>
          </Panel>
        ))}
      </div>

      <Panel label="results on this game" pad={false} className="results-panel">
        {runs.isLoading ? (
          <Loading what="Loading runs" />
        ) : runs.error ? (
          <ErrorState error={runs.error} />
        ) : !runs.data?.length ? (
          <Empty>No runs on this game yet.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>player (best run)</th>
                  <th>kind</th>
                  <th>outcome</th>
                  <th className="num">levels</th>
                  <th className="num">actions</th>
                  <th className="num">vs optimal</th>
                  <th className="num">resets</th>
                  <th className="num">runs</th>
                </tr>
              </thead>
              <tbody>
                {bestByPlayer(runs.data).map((r) => (
                  <tr key={r.run_id}>
                    <td>
                      <Link to={`/replay/${encodeURIComponent(r.run_id)}`}>
                        {r.player?.name ?? r.player?.model_id}
                      </Link>
                      {r.player?.effort && <span className="muted"> · {r.player.effort}</span>}
                    </td>
                    <td className="secondary">{r.player?.kind}</td>
                    <td>
                      <Chip outcome={r.outcome ?? 'IN_PROGRESS'} />
                    </td>
                    <td className="num">
                      {r.levels_completed ?? 0}/{r.levels_total ?? g.levels.length}
                    </td>
                    <td className="num">{r.actions ?? '—'}</td>
                    <td className="num">
                      {r.outcome === 'WIN' && r.actions ? `${(r.actions / Math.max(1, totalOpt)).toFixed(2)}×` : '—'}
                    </td>
                    <td className="num">{r.resets ?? '—'}</td>
                    <td className="num">{r.attempts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}
