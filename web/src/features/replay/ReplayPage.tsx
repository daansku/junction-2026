import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import type { RunMeta } from '@/lib/types'
import { Button, Chip, Empty, ErrorState, Kbd, Loading, PageHeader, Panel } from '@/design/primitives'
import './replay.css'

const SPEEDS = [0.5, 1, 2, 4, 8]

function fmtCost(v?: number) {
  return v == null ? '—' : `$${v.toFixed(v < 0.1 ? 4 : 2)}`
}

function playerLabel(m: RunMeta) {
  return m.player?.name ?? m.player?.model_id ?? '?'
}

export function ReplayIndexPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const gameId = params.get('game_id') ?? undefined
  const runs = useQuery({ queryKey: ['runs', gameId], queryFn: () => api.listRuns({ game_id: gameId }) })
  return (
    <>
      <PageHeader title="Replays" sub={gameId ? <span className="mono">{gameId}</span> : 'All recorded runs.'} />
      {runs.isLoading ? (
        <Loading what="Loading runs" />
      ) : runs.error ? (
        <ErrorState error={runs.error} retry={() => runs.refetch()} />
      ) : !runs.data?.length ? (
        <Empty>No runs recorded yet.</Empty>
      ) : (
        <Panel pad={false}>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>player</th>
                  <th>kind</th>
                  <th>game</th>
                  <th>outcome</th>
                  <th className="num">levels</th>
                  <th className="num">actions</th>
                  <th className="num">resets</th>
                  <th className="num">cost</th>
                  <th>started</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((m) => (
                  <tr key={m.run_id} className="row-link" onClick={() => navigate(`/replay/${encodeURIComponent(m.run_id)}`)}>
                    <td>
                      <Link to={`/replay/${encodeURIComponent(m.run_id)}`} onClick={(e) => e.stopPropagation()}>
                        {playerLabel(m)}
                      </Link>
                      {m.player?.effort && <span className="muted"> · {m.player.effort}</span>}
                    </td>
                    <td className="secondary">{m.player?.kind}</td>
                    <td className="mono">{m.game_id}</td>
                    <td>{m.outcome ? <Chip outcome={m.outcome} /> : <span className="muted">running</span>}</td>
                    <td className="num">
                      {m.levels_completed ?? '—'}/{m.levels_total ?? '—'}
                    </td>
                    <td className="num">{m.actions ?? '—'}</td>
                    <td className="num">{m.resets ?? '—'}</td>
                    <td className="num">{fmtCost(m.cost_usd)}</td>
                    <td className="mono muted">{m.started_at?.replace('T', ' ').slice(0, 19) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  )
}

export function ReplayPage() {
  const { run = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const meta = useQuery({ queryKey: ['run', run], queryFn: () => api.getRun(run) })
  const steps = useQuery({ queryKey: ['steps', run], queryFn: () => api.getRunSteps(run) })
  const n = steps.data?.length ?? 0
  const [idx, setIdx] = useState(() => Number(params.get('step') ?? 0))
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)

  const cur = Math.max(0, Math.min(idx, n - 1))
  const step = steps.data?.[cur]

  // keep ?step= in the URL so a replay position is shareable
  useEffect(() => {
    if (!n) return
    const p = new URLSearchParams(params)
    if (p.get('step') !== String(cur)) {
      p.set('step', String(cur))
      setParams(p, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, n])

  useEffect(() => {
    if (!playing || !n) return
    if (cur >= n - 1) {
      setPlaying(false)
      return
    }
    const t = setTimeout(() => setIdx(cur + 1), 400 / speed)
    return () => clearTimeout(t)
  }, [playing, cur, n, speed])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, textarea, select')) return
      if (e.key === 'ArrowRight') setIdx((i) => Math.min(n - 1, i + 1))
      else if (e.key === 'ArrowLeft') setIdx((i) => Math.max(0, i - 1))
      else if (e.key === ' ') setPlaying((p) => !p)
      else if (e.key === 'Home') setIdx(0)
      else if (e.key === 'End') setIdx(n - 1)
      else if (e.key === ']') setSpeed((s) => SPEEDS[Math.min(SPEEDS.length - 1, SPEEDS.indexOf(s) + 1)])
      else if (e.key === '[') setSpeed((s) => SPEEDS[Math.max(0, SPEEDS.indexOf(s) - 1)])
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [n])

  const levelMarks = useMemo(() => {
    const out: number[] = []
    steps.data?.forEach((s, i) => {
      const prev = steps.data![i - 1]
      if (prev && s.truth?.level !== prev.truth?.level) out.push(i)
    })
    return out
  }, [steps.data])

  if (meta.error) return <ErrorState error={meta.error} retry={() => meta.refetch()} />
  const m = meta.data

  return (
    <>
      <PageHeader
        title={m ? `${playerLabel(m)} — replay` : 'Replay'}
        sub={
          m && (
            <span className="mono">
              {m.game_id} · {m.player?.kind}
              {m.player?.effort ? ` · ${m.player.effort}` : ''}
            </span>
          )
        }
        actions={m?.outcome ? <Chip outcome={m.outcome} /> : null}
      />
      {steps.isLoading ? (
        <Loading what="Loading steps" />
      ) : steps.error ? (
        <ErrorState error={steps.error} retry={() => steps.refetch()} />
      ) : !n ? (
        <Empty>This run has no steps.</Empty>
      ) : (
        <div className="replay-grid">
          <div className="replay-stage">
            <FrameCanvas frame={step?.frame} scale="fit" maxScale={10} />
            <div className="scrubber">
              <Button mono onClick={() => setPlaying((p) => !p)} variant="primary">
                {playing ? 'pause' : 'play'}
              </Button>
              <input
                type="range"
                min={0}
                max={n - 1}
                value={cur}
                onChange={(e) => setIdx(Number(e.target.value))}
                aria-label="Step"
              />
              <span className="mono step-count">
                {cur + 1}/{n}
              </span>
              <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Speed">
                {SPEEDS.map((s) => (
                  <option key={s} value={s}>
                    {s}×
                  </option>
                ))}
              </select>
            </div>
            <div className="timeline" aria-hidden>
              {steps.data!.map((s, i) => (
                <span
                  key={i}
                  className={[
                    'tl-tick',
                    s.action === 'RESET' && 'tl-reset',
                    levelMarks.includes(i) && 'tl-level',
                    i === cur && 'tl-cur',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => setIdx(i)}
                />
              ))}
            </div>
            <div className="muted replay-keys">
              <Kbd>←</Kbd>
              <Kbd>→</Kbd> step · <Kbd>Space</Kbd> play · <Kbd>[</Kbd>
              <Kbd>]</Kbd> speed · <span className="tl-legend tl-level" /> level change ·{' '}
              <span className="tl-legend tl-reset" /> reset
            </div>
          </div>

          <aside className="replay-side">
            <Panel label={`step ${cur + 1} · ${step?.action ?? 'start'}`}>
              <div className="step-fields">
                {step?.reasoning && (
                  <div>
                    <span className="kicker">reasoning</span>
                    <p className="mono model-text">{step.reasoning}</p>
                  </div>
                )}
                {step?.hypothesis && (
                  <div>
                    <span className="kicker">hypothesis</span>
                    <p className="mono model-text">{step.hypothesis}</p>
                  </div>
                )}
                {step?.belief && (
                  <div>
                    <span className="kicker">belief</span> <span className="mono">{step.belief}</span>
                  </div>
                )}
                {!step?.reasoning && !step?.hypothesis && <span className="muted">No model text for this step.</span>}
              </div>
            </Panel>
            {step?.truth && (
              <Panel label="truth — hidden from agents">
                <div className="mono truth-line">
                  L{step.truth.level}/{step.truth.levels_total} · moves {step.truth.moves_used}/{step.truth.move_budget} ·
                  opt {step.truth.optimal_moves}
                  {step.truth.events?.length ? ` · ${step.truth.events.join(', ')}` : ''}
                </div>
              </Panel>
            )}
            <Panel label="steps" pad={false}>
              <ol className="step-list mono">
                {steps.data!.map((s, i) => (
                  <li key={i} className={i === cur ? 'cur' : undefined} onClick={() => setIdx(i)}>
                    <span className="muted">{String(i + 1).padStart(3, ' ')}</span> {s.action ?? 'start'}
                    {s.truth?.events?.length ? <span className="muted"> {s.truth.events.join(',')}</span> : null}
                  </li>
                ))}
              </ol>
            </Panel>
          </aside>
        </div>
      )}
    </>
  )
}
