import { Link } from 'react-router-dom'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { useLiveRuns, type LiveRun } from '@/lib/live'
import { Chip, Empty, ErrorState, PageHeader } from '@/design/primitives'
import './live.css'

const ARROW: Record<string, string> = { ACTION1: '↑', ACTION2: '↓', ACTION3: '←', ACTION4: '→', ACTION5: '␣', RESET: 'R' }

function Tile({ r }: { r: LiveRun }) {
  const m = r.meta
  const t = r.step?.truth
  const href = `/replay/${encodeURIComponent(m.run_id)}`
  return (
    <article className={`live-tile${r.ended ? ' live-ended' : ''}`}>
      <header className="live-head">
        <Link to={href} className="live-name">
          {m.player?.name ?? m.player?.model_id}
        </Link>
        {m.player?.effort && <span className="muted mono">{m.player.effort}</span>}
        <span className="live-chip">
          <Chip outcome={r.ended ? (m.outcome ?? 'ABORTED') : 'IN_PROGRESS'} />
        </span>
      </header>
      <Link to={href} className="live-frame" aria-label={`Open ${m.run_id}`}>
        {r.step ? <FrameCanvas frame={r.step.frame} scale="fit" maxScale={6} /> : <div className="live-wait muted">waiting…</div>}
      </Link>
      <div className="live-facts mono">
        <span>
          L{t?.level ?? '?'}/{t?.levels_total ?? m.levels_total ?? '?'}
        </span>
        <span>{r.step?.i ?? 0} act</span>
        {t?.move_budget != null && (
          <span className="muted">
            {t.moves_used}/{t.move_budget}
          </span>
        )}
        <span className="live-last">{r.step?.action ? (ARROW[r.step.action] ?? r.step.action) : ''}</span>
      </div>
      {r.step?.hypothesis && <p className="live-hyp mono">“{r.step.hypothesis}”</p>}
      <div className="live-game mono muted">{m.game_id}</div>
    </article>
  )
}

export function LiveWall() {
  const { runs, status, error } = useLiveRuns()
  const active = runs.filter((r) => !r.ended).length
  return (
    <>
      <PageHeader
        title="Live"
        sub="Every run in progress on this server, updated step by step. Click a tile to follow it."
        actions={
          <span className="mono muted">
            {active} running · {error ? 'server unreachable, retrying' : status === 'live' ? 'websocket' : status}
          </span>
        }
      />
      {error && !runs.length ? (
        <ErrorState error={error} />
      ) : !runs.length ? (
        <Empty action={<Link to="/play">Start one yourself</Link>}>Nothing is running right now.</Empty>
      ) : (
        <div className="live-grid">
          {runs.map((r) => (
            <Tile key={r.meta.run_id} r={r} />
          ))}
        </div>
      )}
    </>
  )
}
