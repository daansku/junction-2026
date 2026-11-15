import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { isTyping } from '@/lib/keys'
import type { Frame, RunMeta, Step } from '@/lib/types'
import { Button, Chip, Empty, ErrorState, Kbd, Loading, PageHeader, Panel, Stat, cx } from '@/design/primitives'
import { fetchExplanations } from '@/features/play/epistemicApi'
import { conciseSummary, friendlyCause, friendlyRule, friendlyStageShort, truncateQuote } from '@/features/insights/labels'
import { RuleSprite, XrayOverlay } from '@/features/play/XrayOverlay'
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

function eventBadgeClass(ev: string): string {
  if (ev === 'bump' || ev === 'hurt' || ev === 'enemy_hit' || ev === 'caught' || ev === 'checkpoints_reset')
    return 'ev-bad'
  if (ev === 'reset' || ev === 'out_of_moves') return 'ev-warn'
  if (ev === 'level_complete' || ev === 'game_won' || ev === 'opened_door' || ev === 'checkpoint' || ev === 'pit_filled')
    return 'ev-good'
  return 'ev-neutral'
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
  // Aborted runs (abandoned attempts, infra stops, the do-nothing / stop-early stubs) are not listed;
  // their replays stay reachable by direct link. Runs in progress stay, so they can be watched live.
  const sorted = useMemo(
    () =>
      (runs.data ?? [])
        .filter((r) => r.outcome !== 'ABORTED')
        .sort((a, b) => (b.started_at ?? '').localeCompare(a.started_at ?? '')),
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
        sub={gameId ? <span className="mono">{gameId}</span> : 'Every finished or live run, newest first.'}
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
                  <th>Player</th>
                  <th>Kind</th>
                  <th>Game</th>
                  <th>Outcome</th>
                  <th className="num">Levels</th>
                  <th className="num">Actions</th>
                  <th className="num">Resets</th>
                  <th className="num">Tokens</th>
                  <th className="num">Cost</th>
                  <th>Started (UTC)</th>
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

function highlightEvidenceSubstring(text: string, quote?: string | null) {
  if (!quote) return text
  const q = quote.trim()
  if (!q) return text
  const hit = text.indexOf(q)
  if (hit < 0) return text
  return (
    <>
      {text.slice(0, hit)}
      <mark className="forensic-mark">{text.slice(hit, hit + q.length)}</mark>
      {text.slice(hit + q.length)}
    </>
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
  const gameDesc = useQuery({
    queryKey: ['game', meta.data?.game_id],
    queryFn: () => api.getGame(meta.data!.game_id),
    enabled: !!meta.data?.game_id,
    staleTime: Infinity,
  })
  const explanationsQ = useQuery({
    queryKey: ['derived', 'explanations'],
    queryFn: fetchExplanations,
    staleTime: 60_000,
  })

  const n = steps.data?.length ?? 0
  const [idx, setIdx] = useState(() => Number(params.get('step') ?? 0))
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(2)
  const [follow, setFollow] = useState(() => !params.get('step'))
  const [showRulers, setShowRulers] = useState(true)
  const [showGrid, setShowGrid] = useState(false)
  const [xraySplit, setXraySplit] = useState<number | null>(() => {
    const raw = params.get('xray')
    if (raw == null || raw === '') return null
    const v = Number(raw)
    return Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : null
  })
  const [showRuleStrip, setShowRuleStrip] = useState(false)
  const [selectedExpLevel, setSelectedExpLevel] = useState<number | null>(null)
  const listRef = useRef<HTMLOListElement>(null)

  const cur = Math.max(0, Math.min(idx, n - 1))
  const step = steps.data?.[cur]

  useEffect(() => {
    if (live && follow && n) setIdx(n - 1)
  }, [live, follow, n])

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
      else if (e.key === 'x' || e.key === 'X') setXraySplit((v) => (v == null ? 50 : null))
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

  const m = meta.data
  const t = step?.truth
  const curLevel = t?.level ?? 1
  const levelDesc = gameDesc.data?.levels?.find((l) => l.level === curLevel) ?? null

  // Collect up to 6 recent frames on the SAME level ending at `cur` for the ghost trail
  const recentLevelFrames = useMemo(() => {
    const all = steps.data
    if (!all?.length) return []
    const out: Frame[] = []
    for (let k = Math.max(0, cur - 5); k <= cur; k++) {
      if ((all[k]?.truth?.level ?? 1) === curLevel && all[k]?.frame) {
        out.push(all[k].frame)
      }
    }
    return out
  }, [steps.data, cur, curLevel])

  // Failure explanations for this run (user-selected level, else current level, else first failure of run)
  const runExplanations = useMemo(
    () => (explanationsQ.data?.explanations ?? []).filter((e) => e.run_id === run),
    [explanationsQ.data, run],
  )
  const activeExplanation = useMemo(() => {
    if (selectedExpLevel != null) {
      const picked = runExplanations.find((e) => e.level === selectedExpLevel)
      if (picked) return picked
    }
    return runExplanations.find((e) => e.level === curLevel) ?? runExplanations[0] ?? null
  }, [runExplanations, curLevel, selectedExpLevel])

  const seekStepId = (stepId: number, withXray = false) => {
    const arr = steps.data ?? []
    const found = arr.findIndex((s) => s.i === stepId)
    const target = found >= 0 ? found : Math.min(Math.max(0, stepId), Math.max(0, n - 1))
    seek(target)
    if (withXray) setXraySplit((v) => (v == null ? 50 : v))
  }

  if (meta.error) return <ErrorState error={meta.error} retry={() => meta.refetch()} />
  const realState = t?.state === 'WIN' ? 'won' : t?.state === 'GAME_OVER' ? 'lost' : 'playing'
  const beliefMismatch = !!step?.belief && !!t?.state && step.belief !== realState

  const takeoverHref = m
    ? `/play/${encodeURIComponent(m.game_id)}?takeover_run=${encodeURIComponent(run)}&takeover_step=${cur}&takeover_level=${curLevel}&takeover_model=${encodeURIComponent(playerLabel(m))}`
    : null

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
            {takeoverHref && (
              <Link to={takeoverHref}>
                <Button variant="primary" mono title="Jump into a playable session on this level">
                  [ TAKE OVER FROM STEP {cur + 1} ]
                </Button>
              </Link>
            )}
            {m && (
              <Link to={`/replay?game_id=${encodeURIComponent(m.game_id)}`} className="muted">
                other runs
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
            <div className="replay-cartridge-bar mono">
              <span className="muted">
                L{curLevel} · step {cur + 1}/{n}
                {t?.new_rule ? ` · +${t.new_rule}` : ''}
              </span>
              <div className="replay-toggles">
                <Button
                  variant="ghost"
                  mono
                  active={showRulers}
                  onClick={() => setShowRulers((v) => !v)}
                  title="Toggle 0..63 pixel coordinate rulers"
                >
                  rulers
                </Button>
                <Button
                  variant="ghost"
                  mono
                  active={showGrid}
                  onClick={() => setShowGrid((v) => !v)}
                  title="Toggle 64×64 pixel cell grid"
                >
                  grid
                </Button>
                <Button
                  variant="ghost"
                  mono
                  active={xraySplit != null}
                  onClick={() => setXraySplit((v) => (v == null ? 50 : null))}
                  title="Drag the #ffdc00 curtain to contrast raw agent pixels vs hidden engine physics (Key: X)"
                >
                  X-ray {xraySplit != null ? `${xraySplit}%` : 'off'}
                </Button>
              </div>
            </div>

            <div className="replay-canvas-holder">
              <FrameCanvas
                frame={step?.frame}
                scale="fit"
                maxScale={10}
                viewportReserve={140}
                bezel
                rulers={showRulers}
                grid={showGrid}
                xraySplit={xraySplit}
                onXraySplitChange={setXraySplit}
                xrayOverlay={
                  xraySplit != null ? (
                    <XrayOverlay levelDesc={levelDesc} truth={t} recentFrames={recentLevelFrames} />
                  ) : undefined
                }
              />
            </div>

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
              <Kbd>]</Kbd> speed · <Kbd>X</Kbd> x-ray · <span className="tl-legend tl-seg-solved" /> level solved ·{' '}
              <span className="tl-legend tl-reset" /> reset · <span className="tl-legend tl-bad" /> game over
            </div>
          </div>

          <aside className="replay-side">
            {activeExplanation && (
              <Panel
                label={`why this attempt failed · level ${activeExplanation.level}`}
                className="replay-exp-panel"
                actions={
                  <div className="replay-exp-actions">
                    {runExplanations.length > 1 &&
                      runExplanations.map((re) => (
                        <Button
                          key={re.level}
                          variant="ghost"
                          mono
                          active={activeExplanation.level === re.level}
                          onClick={() => {
                            setSelectedExpLevel(re.level)
                            if (re.step != null) seekStepId(re.step, true)
                          }}
                        >
                          L{re.level}
                        </Button>
                      ))}
                    <Chip
                      outcome={
                        activeExplanation.cognitive_stage === 'spatial_planning' ||
                        activeExplanation.cognitive_stage === 'budget_management'
                          ? 'BUDGET'
                          : 'GAME_OVER'
                      }
                    >
                      {friendlyStageShort(activeExplanation.cognitive_stage, activeExplanation.verdict)}
                    </Chip>
                    {activeExplanation.step != null && (
                      <Button
                        variant="primary"
                        mono
                        onClick={() => seekStepId(activeExplanation.step!, true)}
                        title="Seek to divergence step and open 50% X-Ray truth curtain"
                      >
                        [ @STEP {activeExplanation.step} + X-RAY ]
                      </Button>
                    )}
                  </div>
                }
              >
                <div className="replay-exp-body">
                  <div className="replay-exp-meta mono">
                    <span className="replay-exp-badges">
                      {activeExplanation.rule && (
                        <span className="replay-rule-chip">
                          <RuleSprite rule={activeExplanation.rule} size={16} />
                          <strong>{friendlyRule(activeExplanation.rule)}</strong>
                        </span>
                      )}
                      {activeExplanation.root_cause && (
                        <span className="muted">{friendlyCause(activeExplanation.root_cause)}</span>
                      )}
                      {activeExplanation.deduced_rule_in_cot && (
                        <button
                          type="button"
                          className="replay-kd-pill mono"
                          onClick={() => {
                            if (activeExplanation.deduced_rule_step != null) {
                              seekStepId(activeExplanation.deduced_rule_step, false)
                            }
                          }}
                          title="Jump to step where model articulated the hidden rule in CoT/notes"
                        >
                          KNEW RULE{activeExplanation.deduced_rule_step != null ? ` @${activeExplanation.deduced_rule_step}` : ''}
                        </button>
                      )}
                    </span>
                  </div>
                  {(activeExplanation.truth_contrast || activeExplanation.explanation) && (
                    <p className="replay-exp-text">
                      {conciseSummary(activeExplanation.truth_contrast || activeExplanation.explanation)}
                    </p>
                  )}
                  {activeExplanation.evidence_quote && (
                    <blockquote className="replay-exp-quote mono" title={activeExplanation.evidence_quote}>
                      “{truncateQuote(activeExplanation.evidence_quote, 130)}”
                    </blockquote>
                  )}
                </div>
              </Panel>
            )}

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
              <div className={m?.player?.kind === 'model' ? 'step-fields' : 'step-fields step-fields-auto'}>
                {step?.reasoning && (
                  <div>
                    <span className="kicker">
                      {m?.harness_version === 'h2' ? 'extended reasoning' : 'recorded notes'}
                    </span>
                    <p className="mono model-text">
                      {highlightEvidenceSubstring(step.reasoning, activeExplanation?.evidence_quote)}
                    </p>
                  </div>
                )}
                {step?.hypothesis && (
                  <div>
                    <span className="kicker">hypothesis</span>
                    <p className="mono model-text">
                      {highlightEvidenceSubstring(step.hypothesis, activeExplanation?.evidence_quote)}
                    </p>
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
              <Panel
                label="truth · hidden from the player"
                actions={
                  t.new_rule ? (
                    <Button variant="ghost" mono active={showRuleStrip} onClick={() => setShowRuleStrip((v) => !v)}>
                      {showRuleStrip ? 'hide rule strip' : `show ${t.new_rule}`}
                    </Button>
                  ) : null
                }
              >
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
                  <dd className="replay-rules-wrap">
                    {t.active_rules?.length
                      ? t.active_rules.map((r) => (
                          <span key={r} className="replay-rule-chip">
                            <RuleSprite rule={r} size={14} />
                            {r}
                          </span>
                        ))
                      : '—'}
                  </dd>
                  <dt>events</dt>
                  <dd className="replay-events-wrap">
                    {t.events?.length
                      ? t.events.map((ev, k) => (
                          <span key={`${ev}-${k}`} className={cx('ev-pill', eventBadgeClass(ev))}>
                            {ev}
                          </span>
                        ))
                      : '—'}
                  </dd>
                </dl>
                {showRuleStrip && t.new_rule && (
                  <div className="replay-rule-strip">
                    <RuleSprite rule={t.new_rule} mode="strip" />
                  </div>
                )}
              </Panel>
            )}

            <Panel label="steps · accent bar = new hypothesis" pad={false}>
              <ol className="step-list mono" ref={listRef}>
                {steps.data!.map((s, i) => {
                  const hypChanged = !!s.hypothesis && s.hypothesis !== steps.data![i - 1]?.hypothesis
                  return (
                    <li
                      key={i}
                      className={cx(i === cur && 'cur', hypChanged && 'hyp-changed')}
                      onClick={() => seek(i)}
                    >
                      <span className="muted">{String(i + 1).padStart(4, ' ')}</span>{' '}
                      <span className={s.action === 'RESET' ? 'log-reset' : undefined}>
                        {s.action ? (ARROW[s.action] ?? s.action) : '·'}
                      </span>{' '}
                      <span className="muted">L{s.truth?.level ?? '?'}</span>
                      {s.truth?.events?.length ? (
                        <span className="step-ev-inline">
                          {s.truth.events.slice(0, 2).map((ev, k) => (
                            <span key={k} className={cx('ev-pill', eventBadgeClass(ev))}>
                              {ev}
                            </span>
                          ))}
                        </span>
                      ) : null}
                      {hypChanged ? <span className="step-hyp"> “{s.hypothesis}”</span> : null}
                    </li>
                  )
                })}
              </ol>
            </Panel>
          </aside>
        </div>
      )}
    </>
  )
}
