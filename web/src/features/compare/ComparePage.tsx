import { useQueries, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { isTyping } from '@/lib/keys'
import type { Frame, RunMeta, Step } from '@/lib/types'
import { Button, Chip, Empty, ErrorState, Kbd, Loading, PageHeader, Panel } from '@/design/primitives'
import './compare.css'

const MAX_RUNS = 4
const SPEEDS = [1, 2, 4, 8]

interface LevelSlice {
  frames: Frame[] // frames[0] = level start, frames[k] = after k-th action on this level
  actions: number
  resets: number
  solved: boolean
  hypotheses: string[]
}

/** Cut one level out of a run: the actions taken while the player was on `level`. */
function sliceLevel(steps: Step[], level: number): LevelSlice | null {
  const entry = steps.findIndex((s) => (s.truth?.level ?? 1) === level)
  if (entry < 0) return null
  const frames: Frame[] = [steps[entry].frame]
  let resets = 0
  let solved = false
  const hyps: string[] = []
  for (let k = entry + 1; k < steps.length; k++) {
    if ((steps[k - 1].truth?.level ?? 1) !== level) break
    frames.push(steps[k].frame)
    if (steps[k].action === 'RESET') resets++
    const h = steps[k].hypothesis
    if (h && h !== hyps[hyps.length - 1]) hyps.push(h)
    const t = steps[k].truth
    if ((t?.level ?? level) > level || t?.state === 'WIN') {
      solved = true
      break
    }
  }
  return { frames, actions: frames.length - 1, resets, solved, hypotheses: hyps }
}

function label(m: RunMeta) {
  return `${m.player?.name ?? m.player?.model_id}${m.player?.effort ? ` · ${m.player.effort}` : ''}`
}

/** Default picks: optimal baseline, best human, best two models. */
function defaultPicks(runs: RunMeta[]): string[] {
  const score = (r: RunMeta) => (r.levels_completed ?? 0) * 1e6 - (r.actions ?? 0)
  const best = (f: (r: RunMeta) => boolean, n = 1) =>
    runs
      .filter(f)
      .sort((a, b) => score(b) - score(a))
      .slice(0, n)
  const opt = best((r) => r.player?.kind === 'baseline' && /optimal/.test(r.player?.name ?? r.player?.model_id ?? ''))
  const human = best(
    (r) =>
      r.player?.kind === 'human' &&
      !/^(anonymous|anon|test|test2|practice|debug|visitor)?$/i.test((r.player?.name ?? '').trim()) &&
      !(r.player as unknown as Record<string, unknown> | undefined)?.purpose,
  )
  // Best run of each model, then the two best models: two runs of one model compare less.
  const seen = new Set<string>()
  const models = best((r) => r.player?.kind === 'model', Infinity)
    .filter((r) => {
      const id = r.player?.model_id ?? r.player?.name ?? r.run_id
      if (seen.has(id)) return false
      seen.add(id)
      return true
    })
    .slice(0, 2)
  return [...opt, ...human, ...models].slice(0, MAX_RUNS).map((r) => r.run_id)
}

export function ComparePage() {
  const [params, setParams] = useSearchParams()
  const setParam = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }

  const games = useQuery({ queryKey: ['games', undefined], queryFn: () => api.listGames() })
  const gameId = params.get('game') ?? games.data?.[0]?.game_id
  const level = Number(params.get('level') ?? 1)
  const game = useQuery({ queryKey: ['game', gameId], queryFn: () => api.getGame(gameId!), enabled: !!gameId })
  const runs = useQuery({
    queryKey: ['runs', gameId, undefined],
    queryFn: () => api.listRuns({ game_id: gameId }),
    enabled: !!gameId,
  })
  // finished runs, plus runs still playing that already cleared this level (their attempt on it is complete)
  const finished = useMemo(
    () => (runs.data ?? []).filter((r) => r.outcome !== 'IN_PROGRESS' || (r.levels_completed ?? 0) >= level),
    [runs.data, level],
  )
  const picked = useMemo(() => {
    const p = params.get('runs')
    return p ? p.split(',').filter(Boolean) : defaultPicks(finished)
  }, [params, finished])

  const stepQs = useQueries({
    queries: picked.map((id) => ({ queryKey: ['steps', id], queryFn: () => api.getRunSteps(id), staleTime: Infinity })),
  })

  const slices = picked.map((id, i) => {
    const steps = stepQs[i]?.data
    return { id, meta: finished.find((r) => r.run_id === id), slice: steps ? sliceLevel(steps, level) : undefined, q: stepQs[i] }
  })
  const maxLen = Math.max(1, ...slices.map((s) => s.slice?.frames.length ?? 1))

  const [k, setK] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(2)
  useEffect(() => setK(0), [gameId, level, picked.join(',')])
  useEffect(() => {
    if (!playing) return
    if (k >= maxLen - 1) return setPlaying(false)
    const t = setTimeout(() => setK(k + 1), 400 / speed)
    return () => clearTimeout(t)
  }, [playing, k, maxLen, speed])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return
      if (e.key === 'ArrowRight') setK((x) => Math.min(maxLen - 1, x + 1))
      else if (e.key === 'ArrowLeft') setK((x) => Math.max(0, x - 1))
      else if (e.key === ' ') setPlaying((p) => !p)
      else if (e.key === 'Home') setK(0)
      else if (e.key === 'End') setK(maxLen - 1)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [maxLen])

  const toggleRun = (id: string) => {
    const next = picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id].slice(-MAX_RUNS)
    setParam('runs', next.join(','))
  }

  const lv = game.data?.levels.find((l) => l.level === level)
  const nLevels = game.data?.levels.length ?? game.data?.levels_total ?? 0

  return (
    <>
      <PageHeader
        title="Compare"
        sub="Same level, side by side. Steps are aligned by action count on the level."
        actions={
          <label className="field">
            <span className="kicker">game</span>
            <select
              value={gameId ?? ''}
              onChange={(e) => {
                const p = new URLSearchParams()
                p.set('game', e.target.value)
                setParams(p, { replace: true })
              }}
            >
              {gameId && !games.data?.some((g) => g.game_id === gameId) && <option value={gameId}>{gameId}</option>}
              {games.data?.map((g) => (
                <option key={g.game_id} value={g.game_id}>
                  {g.game_id}
                </option>
              ))}
            </select>
          </label>
        }
      />

      {games.error && <ErrorState error={games.error} />}

      <div className="cmp-levels" role="tablist" aria-label="Level">
        {Array.from({ length: nLevels }, (_, i) => i + 1).map((n) => {
          const l = game.data?.levels.find((x) => x.level === n)
          return (
            <button
              key={n}
              role="tab"
              aria-selected={n === level}
              className={`cmp-level-tab${n === level ? ' active' : ''}`}
              onClick={() => setParam('level', String(n))}
            >
              <span className="mono">L{n}</span>
              {l?.new_rule && <span className="cmp-tab-rule mono">+{l.new_rule}</span>}
            </button>
          )
        })}
      </div>

      {lv && (
        <p className="secondary cmp-levelinfo mono">
          rules {lv.rules.length ? lv.rules.join(', ') : 'walls, goal'} · optimal {lv.optimal_moves} · budget{' '}
          {lv.move_budget}
          {lv.new_rule ? ` · introduces ${lv.new_rule}` : ''}
        </p>
      )}

      {runs.isLoading ? (
        <Loading what="Loading runs" />
      ) : !finished.length ? (
        <Empty action={gameId && <Link to={`/play/${encodeURIComponent(gameId)}`}>Play it</Link>}>
          No finished runs on this game yet.
        </Empty>
      ) : (
        <>
          <div className="cmp-controls">
            <Button mono variant="primary" onClick={() => setPlaying((p) => !p)}>
              {playing ? 'pause' : 'play'}
            </Button>
            <input
              type="range"
              min={0}
              max={maxLen - 1}
              value={Math.min(k, maxLen - 1)}
              onChange={(e) => setK(Number(e.target.value))}
              aria-label="Action on level"
            />
            <span className="mono step-count">
              {k}/{maxLen - 1}
            </span>
            <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Speed">
              {SPEEDS.map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
            <span className="muted cmp-keys">
              <Kbd>←</Kbd>
              <Kbd>→</Kbd> step · <Kbd>Space</Kbd> play
            </span>
          </div>

          <div className="cmp-grid" style={{ ['--cols' as string]: Math.max(1, slices.length) }}>
            {slices.map(({ id, meta, slice, q }) => {
              const kk = Math.min(k, (slice?.frames.length ?? 1) - 1)
              const done = slice && k >= slice.frames.length - 1
              return (
                <Panel
                  key={id}
                  label={meta ? label(meta) : id}
                  actions={meta && <span className="muted mono">{meta.player?.kind}</span>}
                  className="cmp-cell"
                >
                  {q?.isLoading ? (
                    <Loading what="Loading steps" />
                  ) : q?.error ? (
                    <ErrorState error={q.error} />
                  ) : !slice ? (
                    <div className="cmp-never muted">Never reached level {level}.</div>
                  ) : (
                    <>
                      <FrameCanvas frame={slice.frames[kk]} scale="fit" maxScale={8} />
                      <div className="cmp-status mono">
                        <span>
                          {kk}/{slice.actions} actions
                        </span>
                        {slice.resets > 0 && <span className="log-reset">{slice.resets} resets</span>}
                        {done && (
                          <span className="cmp-chip">
                            {slice.solved ? <Chip outcome="WIN">SOLVED</Chip> : <Chip outcome="GAME_OVER">NOT SOLVED</Chip>}
                          </span>
                        )}
                      </div>
                    </>
                  )}
                </Panel>
              )
            })}
          </div>

          <Panel label={`level ${level} · summary`} pad={false} className="cmp-summary">
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Solved</th>
                    <th className="num">Actions</th>
                    <th className="num">Vs optimal</th>
                    <th className="num">Resets</th>
                    <th>Hypotheses on this level</th>
                  </tr>
                </thead>
                <tbody>
                  {slices.map(({ id, meta, slice }) => (
                    <tr key={id}>
                      <td>
                        <Link to={`/replay/${encodeURIComponent(id)}`}>{meta ? label(meta) : id}</Link>
                      </td>
                      <td>{slice ? (slice.solved ? 'yes' : 'no') : '—'}</td>
                      <td className="num">{slice?.actions ?? '—'}</td>
                      <td className="num">
                        {slice?.solved && lv?.optimal_moves ? `${(slice.actions / lv.optimal_moves).toFixed(2)}×` : '—'}
                      </td>
                      <td className="num">{slice?.resets ?? '—'}</td>
                      <td className="cmp-hyps mono">
                        {slice?.hypotheses.length ? slice.hypotheses.slice(0, 3).map((h, i) => <div key={i}>“{h}”</div>) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel label={`runs on this game · pick up to ${MAX_RUNS}`} pad={false}>
            <div className="table-wrap cmp-picker">
              <table className="table">
                <tbody>
                  {finished.map((r) => (
                    <tr key={r.run_id} className="row-link" onClick={() => toggleRun(r.run_id)}>
                      <td style={{ width: 28 }}>
                        <input
                          type="checkbox"
                          checked={picked.includes(r.run_id)}
                          onChange={() => toggleRun(r.run_id)}
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Compare ${label(r)}`}
                        />
                      </td>
                      <td>{label(r)}</td>
                      <td className="secondary">{r.player?.kind}</td>
                      <td>{r.outcome && <Chip outcome={r.outcome} />}</td>
                      <td className="num">
                        {r.levels_completed ?? 0}/{r.levels_total ?? '?'}
                      </td>
                      <td className="num">{r.actions ?? '—'} act</td>
                      <td className="mono muted">{r.started_at?.slice(0, 16).replace('T', ' ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </>
  )
}
