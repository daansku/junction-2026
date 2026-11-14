import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { isTyping } from '@/lib/keys'
import type { RunMeta, Step } from '@/lib/types'
import { Button, Chip, Empty, ErrorState, Kbd, Loading, PageHeader, Panel, Stat } from '@/design/primitives'
import './replay.css'

const SPEEDS = [0.5, 1, 2, 4, 8, 16]

const ARROW: Record<string, string> = {
  ACTION1: '↑',
  ACTION2: '↓',
  ACTION3: '←',
  ACTION4: '→',
  ACTION5: '␣',
  RESET: 'R',
}

export function fmtCost(v?: number | null) {
  return v == null ? '—' : `$${v.toFixed(v < 0.1 ? 4 : 2)}`
}
function fmtInt(v?: number | null) {
  return v == null ? '—' : v.toLocaleString('en-US')
}
function fmtDur(s?: number | null) {
  if (s == null) return '—'
  if (s < 60) return `${s.toFixed(0)}s`
  return `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`
}

export function playerLabel(m: RunMeta) {
  return m.player?.name ?? m.player?.model_id ?? '?'
}

function isLive(m?: RunMeta) {
  return !!m && (m.outcome === 'IN_PROGRESS' || (!m.outcome && !m.ended_at))
}

// ---------------- index ----------------

export function ReplayIndexPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const gameId = params.get('game_id') ?? undefined
  const kind = params.get('kind') ?? undefined
  const runs = useQuery({
    queryKey: ['runs', gameId, kind],
    queryFn: () => api.listRuns({ game_id: gameId, kind }),
    refetchInterval: 10_000,
  })
  const sorted = useMemo(
    () => [...(runs.data ?? [])].sort((a, b) => (b.started_at ?? '').localeCompare(a.started_at ?? '')),
    [runs.data],
  )
  const setParam = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }

  return (
    <>
      <PageHeader
        title="Replays"
        sub={gameId ? <span className="mono">{gameId}</span> : 'Every recorded run, newest first.'}
        actions={
          <>
            <label className="field">
              <span className="kicker">player</span>
              <select value={kind ?? ''} onChange={(e) => setParam('kind', e.target.value)}>
                <option value="">all</option>
                <option value="model">model</option>
                <option value="human">human</option>
                <option value="baseline">baseline</option>
              </select>
            </label>
            {gameId && (
              <Button variant="ghost" onClick={() => setParam('game_id', '')}>
                all games
              </Button>
            )}
          </>
        }
      />
      {runs.isLoading ? (
        <Loading what="Loading runs" />
      ) : runs.error ? (
        <ErrorState error={runs.error} retry={() => runs.refetch()} />
      ) : !sorted.length ? (
        <Empty>No runs recorded yet.</Empty>
      ) : (
        <Panel pad={false} label={`${sorted.length} runs`}>
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
                  <th className="num">tokens</th>
                  <th className="num">cost</th>
                  <th>started (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((m) => (
                  <tr
                    key={m.run_id}
                    className="row-link"
                    onClick={() => navigate(`/replay/${encodeURIComponent(m.run_id)}`)}
                  >
                    <td>
                      <Link to={`/replay/${encodeURIComponent(m.run_id)}`} onClick={(e) => e.stopPropagation()}>
                        {playerLabel(m)}
                      </Link>
                      {m.player?.effort && <span className="muted"> · {m.player.effort}</span>}
                    </td>
                    <td className="secondary">{m.player?.kind}</td>
                    <td className="mono">
                      <a
                        href={`?game_id=${encodeURIComponent(m.game_id)}`}
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          setParam('game_id', m.game_id)
                        }}
                      >
                        {m.game_id}
                      </a>
                    </td>
                    <td>{m.outcome ? <Chip outcome={m.outcome} /> : <Chip outcome="IN_PROGRESS" />}</td>
                    <td className="num">
                      {m.levels_completed ?? '—'}/{m.levels_total ?? '—'}
                    </td>
                    <td className="num">{fmtInt(m.actions)}</td>
                    <td className="num">{fmtInt(m.resets)}</td>
                    <td className="num">{m.tokens_in ? fmtInt((m.tokens_in ?? 0) + (m.tokens_out ?? 0)) : '—'}</td>
                    <td className="num">{m.cost_usd ? fmtCost(m.cost_usd) : '—'}</td>
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

// ---------------- single run ----------------

interface Segment {
  level: number
  from: number
  to: number // inclusive
  newRule?: string | null
  solved: boolean
}

function levelSegments(steps: Step[], levelsCompleted?: number): Segment[] {
  const segs: Segment[] = []
  steps.forEach((s, i) => {
    const lv = s.truth?.level ?? 1
    const last = segs[segs.length - 1]
    if (!last || last.level !== lv) {
      if (last) last.solved = lv > last.level
      segs.push({ level: lv, from: i, to: i, newRule: s.truth?.new_rule ?? null, solved: false })
    } else last.to = i
  })
  const last = segs[segs.length - 1]
  if (last && steps[steps.length - 1]?.truth?.state === 'WIN') last.solved = true
  if (last && levelsCompleted != null && last.level <= levelsCompleted) last.solved = true
  return segs
}

function Timeline({
  steps,
  cur,
  onSeek,
  segments,
}: {
  steps: Step[]
  cur: number
  onSeek: (i: number) => void
  segments: Segment[]
}) {
  const n = steps.length
  const pct = (i: number) => `${(i / Math.max(1, n)) * 100}%`
  const seek = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    onSeek(Math.max(0, Math.min(n - 1, Math.floor(((e.clientX - r.left) / r.width) * n))))
  }
  return (
    <div className="timeline-wrap">
      <div className="tl-levels" onClick={seek}>
        {segments.map((s, k) => (
          <span
            key={k}
            className={`tl-seg ${s.solved ? 'tl-seg-solved' : ''}`}
            style={{ left: pct(s.from), width: pct(s.to - s.from + 1) }}
            title={`Level ${s.level}${s.newRule ? ` · new: ${s.newRule}` : ''} · steps ${s.from + 1}–${s.to + 1}`}
          >
            <span className="tl-seg-label mono">
              L{s.level}
              {s.newRule ? ` +${s.newRule}` : ''}
            </span>
          </span>
        ))}
      </div>
      <div
        className="tl-track"
        onClick={seek}
        role="slider"
        aria-valuemin={1}
        aria-valuemax={n}
        aria-valuenow={cur + 1}
        aria-label="Timeline"
      >
        {steps.map((s, i) =>
          s.action === 'RESET' ? <span key={i} className="tl-mark tl-reset" style={{ left: pct(i) }} /> : null,
        )}
        {steps.map((s, i) =>
          s.truth?.state === 'GAME_OVER' && steps[i - 1]?.truth?.state !== 'GAME_OVER' ? (
            <span key={`e${i}`} className="tl-mark tl-bad" style={{ left: pct(i) }} />
          ) : null,
        )}
        <span className="tl-cursor" style={{ left: pct(cur) }} />
      </div>
    </div>
  )
}

export function ReplayPage() {
  const { run = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const meta = useQuery({
    queryKey: ['run', run],
    queryFn: () => api.getRun(run),
    refetchInterval: (q) => (isLive(q.state.data) ? 2000 : false),
  })
  const live = isLive(meta.data)
  const steps = useQuery({
    queryKey: ['steps', run],
    queryFn: () => api.getRunSteps(run),
    refetchInterval: live ? 1500 : false,
  })
  const n = steps.data?.length ?? 0
  const [idx, setIdx] = useState(() => Number(params.get('step') ?? 0))
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(2)
  const [follow, setFollow] = useState(() => !params.get('step'))
  const listRef = useRef<HTMLOListElement>(null)

  const cur = Math.max(0, Math.min(idx, n - 1))
  const step = steps.data?.[cur]

  // live: follow the newest step unless the viewer scrubbed away
  useEffect(() => {
    if (live && follow && n) setIdx(n - 1)
  }, [live, follow, n])

  // keep ?step= in the URL so a replay position is shareable
  useEffect(() => {
    if (!n || live) return
    const p = new URLSearchParams(params)
    if (p.get('step') !== String(cur)) {
      p.set('step', String(cur))
      setParams(p, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, n, live])

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
    const list = listRef.current
    const el = list?.querySelector('li.cur') as HTMLElement | null
    if (list && el) {
      const top = el.offsetTop - list.offsetTop
      if (top < list.scrollTop || top > list.scrollTop + list.clientHeight - el.clientHeight)
        list.scrollTop = top - list.clientHeight / 2
    }
  }, [cur])

  const seek = (i: number) => {
    setFollow(false)
    setIdx(i)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return
      if (e.key === 'ArrowRight') seek(Math.min(n - 1, cur + (e.shiftKey ? 10 : 1)))
      else if (e.key === 'ArrowLeft') seek(Math.max(0, cur - (e.shiftKey ? 10 : 1)))
      else if (e.key === ' ') setPlaying((p) => !p)
      else if (e.key === 'Home') seek(0)
      else if (e.key === 'End') seek(n - 1)
      else if (e.key === ']') setSpeed((s) => SPEEDS[Math.min(SPEEDS.length - 1, SPEEDS.indexOf(s) + 1)])
      else if (e.key === '[') setSpeed((s) => SPEEDS[Math.max(0, SPEEDS.indexOf(s) - 1)])
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const segments = useMemo(
    () => levelSegments(steps.data ?? [], meta.data?.levels_completed),
    [steps.data, meta.data?.levels_completed],
  )

  if (meta.error) return <ErrorState error={meta.error} retry={() => meta.refetch()} />
  const m = meta.data
  const t = step?.truth
  const realState = t?.state === 'WIN' ? 'won' : t?.state === 'GAME_OVER' ? 'lost' : 'playing'
  const beliefMismatch = !!step?.belief && !!t?.state && step.belief !== realState

  return (
    <>
      <PageHeader
        title={m ? playerLabel(m) : 'Replay'}
        sub={
          m && (
            <span className="mono">
              <Link to={`/gallery/${encodeURIComponent(m.game_id)}`}>{m.game_id}</Link> · {m.player?.kind}
              {m.player?.model_id && m.player.model_id !== m.player.name ? ` · ${m.player.model_id}` : ''}
              {m.player?.provider ? ` · ${m.player.provider}` : ''}
              {m.player?.effort ? ` · effort ${m.player.effort}` : ''}
              {m.harness_version ? ` · harness ${m.harness_version}` : ''}
            </span>
          )
        }
        actions={
          <>
            {m && <Chip outcome={m.outcome ?? 'IN_PROGRESS'} />}
            {m && (
              <Link to={`/replay?game_id=${encodeURIComponent(m.game_id)}`} className="muted">
                other runs on this game
              </Link>
            )}
          </>
        }
      />

      {m && (
        <div className="run-stats">
          <Stat label="levels" value={`${m.levels_completed ?? 0}/${m.levels_total ?? '?'}`} />
          <Stat label="actions" value={fmtInt(m.actions ?? n)} />
          <Stat label="resets" value={fmtInt(m.resets)} />
          {!!m.tokens_in && <Stat label="tokens in / out" value={`${fmtInt(m.tokens_in)} / ${fmtInt(m.tokens_out)}`} />}
          {!!m.cost_usd && <Stat label="cost" value={fmtCost(m.cost_usd)} />}
          <Stat label="wall" value={fmtDur(m.wall_s)} />
          {m.end_reason && <Stat label="end reason" value={<span className="end-reason">{m.end_reason}</span>} />}
        </div>
      )}

      {steps.isLoading ? (
        <Loading what="Loading steps" />
      ) : steps.error ? (
        <ErrorState error={steps.error} retry={() => steps.refetch()} />
      ) : !n ? (
        <Empty>{live ? 'Waiting for the first step…' : 'This run has no steps.'}</Empty>
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
                onChange={(e) => seek(Number(e.target.value))}
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
              {live && (
                <Button mono active={follow} onClick={() => setFollow((f) => !f)} title="Jump to newest step">
                  follow
                </Button>
              )}
            </div>
            <Timeline steps={steps.data!} cur={cur} onSeek={seek} segments={segments} />
            <div className="muted replay-keys">
              <Kbd>←</Kbd>
              <Kbd>→</Kbd> step (<Kbd>Shift</Kbd> ×10) · <Kbd>Space</Kbd> play · <Kbd>[</Kbd>
              <Kbd>]</Kbd> speed · <span className="tl-legend tl-seg-solved" /> level solved ·{' '}
              <span className="tl-legend tl-reset" /> reset · <span className="tl-legend tl-bad" /> game over
            </div>
          </div>

          <aside className="replay-side">
            <Panel
              label={`step ${cur + 1} · ${step?.action ?? 'start'}`}
              actions={
                step?.usage?.in || step?.latency_ms ? (
                  <span className="mono muted step-usage">
                    {!!step?.usage?.in && `${fmtInt(step.usage.in)} in · ${fmtInt(step.usage.out)} out`}
                    {!!step?.latency_ms && ` · ${(step.latency_ms / 1000).toFixed(1)}s`}
                  </span>
                ) : null
              }
            >
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
                  <div className="belief-line">
                    <span className="kicker">belief</span> <span className="mono">{step.belief}</span>
                    {t?.state && (
                      <span className={beliefMismatch ? 'belief-bad mono' : 'muted mono'}>
                        {beliefMismatch ? `≠ actually ${realState}` : '= correct'}
                      </span>
                    )}
                  </div>
                )}
                {!step?.reasoning && !step?.hypothesis && !step?.belief && (
                  <span className="muted">
                    {m?.player?.kind === 'model'
                      ? 'No model text on this step.'
                      : `No reasoning recorded for ${m?.player?.kind ?? 'this'} players.`}
                  </span>
                )}
              </div>
            </Panel>
            {t && (
              <Panel label="truth · hidden from the player">
                <dl className="truth mono">
                  <dt>state</dt>
                  <dd>
                    <Chip outcome={t.state} />
                  </dd>
                  <dt>level</dt>
                  <dd>
                    {t.level}/{t.levels_total}
                    {t.new_rule ? ` · introduces ${t.new_rule}` : ''}
                  </dd>
                  <dt>moves</dt>
                  <dd>
                    {t.moves_used}/{t.move_budget} · optimal {t.optimal_moves}
                  </dd>
                  <dt>rules</dt>
                  <dd>{t.active_rules?.join(', ') || '—'}</dd>
                  <dt>events</dt>
                  <dd>{t.events?.join(', ') || '—'}</dd>
                </dl>
              </Panel>
            )}
            <Panel label="steps" pad={false}>
              <ol className="step-list mono" ref={listRef}>
                {steps.data!.map((s, i) => (
                  <li key={i} className={i === cur ? 'cur' : undefined} onClick={() => seek(i)}>
                    <span className="muted">{String(i + 1).padStart(4, ' ')}</span>{' '}
                    <span className={s.action === 'RESET' ? 'log-reset' : undefined}>
                      {s.action ? (ARROW[s.action] ?? s.action) : '·'}
                    </span>{' '}
                    <span className="muted">L{s.truth?.level ?? '?'}</span>
                    {s.truth?.events?.length ? <span className="secondary"> {s.truth.events.join(', ')}</span> : null}
                    {s.hypothesis && s.hypothesis !== steps.data![i - 1]?.hypothesis ? (
                      <span className="step-hyp"> “{s.hypothesis}”</span>
                    ) : null}
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
