import * as Plot from '@observablehq/plot'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Button,
  Chip,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Panel,
  Stat,
  cx,
} from '@/design/primitives'
import { api } from '@/lib/api'
import { PlotFigure, cssVar, seriesColors } from '@/lib/PlotFigure'
import type { RunMeta } from '@/lib/types'
import { fetchExplanations } from '@/features/play/epistemicApi'
import { RuleSprite } from '@/features/play/XrayOverlay'
import type { RuleCell, RulesDocument, InsightsDocument } from './types'
import './insights.css'

type MatrixMetric =
  | 'recombined_solve_rate'
  | 'intro_solve_rate'
  | 'actions_to_first_use'
  | 'wasted_actions'
  | 'hypothesis_match_rate'
  | 'repeated_no_effect_actions'

const METRIC_META: Record<
  MatrixMetric,
  { label: string; short: string; isRate?: boolean; introOnly?: boolean; higherBetter: boolean }
> = {
  recombined_solve_rate: {
    label: 'Recombined solve rate',
    short: 'Recomb Solve',
    isRate: true,
    higherBetter: true,
  },
  intro_solve_rate: {
    label: 'Intro solve rate',
    short: 'Intro Solve',
    isRate: true,
    introOnly: true,
    higherBetter: true,
  },
  actions_to_first_use: {
    label: 'Actions to first rule use',
    short: 'First Use',
    introOnly: true,
    higherBetter: false,
  },
  wasted_actions: {
    label: 'Wasted actions (vs optimal)',
    short: 'Wasted Act',
    introOnly: true,
    higherBetter: false,
  },
  hypothesis_match_rate: {
    label: 'Hypothesis match rate',
    short: 'Hyp Match',
    isRate: true,
    introOnly: true,
    higherBetter: true,
  },
  repeated_no_effect_actions: {
    label: 'No-effect loop actions',
    short: 'No-Effect',
    introOnly: true,
    higherBetter: false,
  },
}

const SEVERITY_OUTCOME: Record<string, string> = {
  high: 'GAME_OVER',
  medium: 'BUDGET',
  info: 'WIN',
}

function cellMetricValue(cell: RuleCell, metric: MatrixMetric): number | null {
  if (METRIC_META[metric].introOnly && cell.intro_levels === 0) {
    return null
  }
  const raw = cell[metric]
  return typeof raw === 'number' && !Number.isNaN(raw) ? raw : null
}

function formatMetric(val: number | null | undefined, metric: MatrixMetric): string {
  if (val == null || Number.isNaN(val)) return 'n/a'
  if (METRIC_META[metric].isRate) return `${(val * 100).toFixed(0)}%`
  return val % 1 === 0 ? String(val) : val.toFixed(1)
}

function cellLabel(cell: RuleCell): string {
  return cell.effort ? `${cell.player_id} (${cell.effort})` : cell.player_id
}

function shortPlayerHeader(label: string): string {
  const s = label
    .replace(/^verda-/, '')
    .replace(/^featherless-/, '')
    .replace(/^modal-/, '')
    .replace(/-super-vl$/, '')
    .replace(/-pro$/, '')
  return s.length > 14 ? s.slice(0, 13) + '…' : s
}

function shortRunId(runId: string): string {
  const tail = runId.includes('-') ? runId.split('-').pop()! : runId
  return tail.slice(-6)
}

export function InsightsPage() {
  const insightsQ = useQuery({
    queryKey: ['derived', 'insights'],
    queryFn: () => api.derived<InsightsDocument>('insights'),
  })
  const rulesQ = useQuery({
    queryKey: ['derived', 'rules'],
    queryFn: () => api.derived<RulesDocument>('rules'),
  })
  const explanationsQ = useQuery({
    queryKey: ['derived', 'explanations'],
    queryFn: fetchExplanations,
    staleTime: 60_000,
  })
  const runsQ = useQuery({
    queryKey: ['runs', 'ins-lookup'],
    queryFn: () => api.listRuns(),
    staleTime: 60_000,
  })

  const [metric, setMetric] = useState<MatrixMetric>('recombined_solve_rate')
  const [matrixMode, setMatrixMode] = useState<'plot' | 'table'>('plot')
  const [curveMode, setCurveMode] = useState<'plot' | 'table'>('plot')
  const [selectedCell, setSelectedCell] = useState<RuleCell | null>(null)
  const [expRuleFilter, setExpRuleFilter] = useState<string>('all')
  const [expStageFilter, setExpStageFilter] = useState<string>('all')
  const [expModelFilter, setExpModelFilter] = useState<string>('all')

  const insights = insightsQ.data?.insights ?? []
  const cells = rulesQ.data?.cells ?? []
  const learningCurve = rulesQ.data?.level_curve ?? rulesQ.data?.level_learning_curve ?? []
  const failureModes = rulesQ.data?.failure_modes ?? []
  const explanations = explanationsQ.data?.explanations ?? []
  const expSummary = explanationsQ.data?.summary ?? null

  const runById = useMemo(() => {
    const map = new Map<string, RunMeta>()
    for (const r of runsQ.data ?? []) map.set(r.run_id, r)
    return map
  }, [runsQ.data])

  const buildTakeoverHref = (
    runId: string,
    step?: number | null,
    level?: number | null,
    gameIdOverride?: string | null,
    playerOverride?: string | null,
  ): string | null => {
    const rm = runById.get(runId)
    const gid = gameIdOverride || rm?.game_id
    if (!gid) return null
    const p = new URLSearchParams()
    p.set('takeover_run', runId)
    if (step != null) p.set('takeover_step', String(step))
    if (level != null) p.set('takeover_level', String(level))
    const who = playerOverride || rm?.player?.name || rm?.player?.model_id
    if (who) p.set('takeover_model', who)
    return `/play/${encodeURIComponent(gid)}?${p.toString()}`
  }

  const totalFailureEvents = useMemo(
    () => failureModes.reduce((acc, f) => acc + f.count, 0),
    [failureModes],
  )
  const maxFailureCount = useMemo(
    () => Math.max(1, ...failureModes.map((f) => f.count)),
    [failureModes],
  )

  // Ordered rules & players for the 8-col square-cell heatmap matrix
  const matrixGrid = useMemo(() => {
    const rulesOrder = Array.from(new Set(cells.map((c) => c.rule)))
    const playersOrder = Array.from(new Set(cells.map((c) => cellLabel(c))))
    const lookup = new Map<string, RuleCell>()
    let minVal = Infinity
    let maxVal = -Infinity
    for (const c of cells) {
      const k = `${c.rule}::${cellLabel(c)}`
      lookup.set(k, c)
      const v = cellMetricValue(c, metric)
      if (v != null) {
        if (v < minVal) minVal = v
        if (v > maxVal) maxVal = v
      }
    }
    if (METRIC_META[metric].isRate) {
      minVal = 0
      maxVal = 1
    } else if (!Number.isFinite(minVal)) {
      minVal = 0
      maxVal = 1
    } else if (Math.abs(maxVal - minVal) < 1e-6) {
      maxVal = minVal + 1
    }
    return { rulesOrder, playersOrder, lookup, minVal, maxVal }
  }, [cells, metric])

  const curvePlayers = useMemo(() => {
    const unique = Array.from(new Set(learningCurve.map((p) => p.player_id)))
    if (unique.length <= 4) return learningCurve
    const scoreByPlayer = new Map<string, number>()
    const countByPlayer = new Map<string, number>()
    for (const pt of learningCurve) {
      scoreByPlayer.set(pt.player_id, (scoreByPlayer.get(pt.player_id) ?? 0) + pt.mean_score)
      countByPlayer.set(pt.player_id, (countByPlayer.get(pt.player_id) ?? 0) + 1)
    }
    const ranked = [...unique].sort((a, b) => {
      const ma = (scoreByPlayer.get(a) ?? 0) / Math.max(1, countByPlayer.get(a) ?? 1)
      const mb = (scoreByPlayer.get(b) ?? 0) / Math.max(1, countByPlayer.get(b) ?? 1)
      if (Math.abs(mb - ma) > 1e-6) return mb - ma
      const aBase = a === 'noop' || a === 'stop_early' || a === 'random' ? 1 : 0
      const bBase = b === 'noop' || b === 'stop_early' || b === 'random' ? 1 : 0
      return aBase - bBase
    })
    const keep = new Set(ranked.slice(0, 4))
    return learningCurve.filter((p) => keep.has(p.player_id))
  }, [learningCurve])

  const activeCell = selectedCell ?? cells.find((c) => c.intro_levels > 0 && c.player_id !== 'optimal') ?? cells[0] ?? null

  const cellExplanations = useMemo(() => {
    if (!activeCell) return []
    return explanations
      .filter((e) => e.rule === activeCell.rule && (!e.player_id || e.player_id.startsWith(activeCell.player_id)))
      .slice(0, 2)
  }, [explanations, activeCell])

  const explanationRules = useMemo(
    () => ['all', ...Array.from(new Set(explanations.map((e) => e.rule).filter((r): r is string => !!r))).sort()],
    [explanations],
  )
  const filteredExplanations = useMemo(() => {
    return explanations.filter((e) => {
      if (expRuleFilter !== 'all' && e.rule !== expRuleFilter) return false
      if (expModelFilter !== 'all' && `${e.player_id ?? ''}::${e.harness_version ?? 'h1'}` !== expModelFilter) return false
      if (expStageFilter === 'all') return true
      if (expStageFilter === 'knowing_doing') return !!e.deduced_rule_in_cot
      if (expStageFilter === 'h2') return e.harness_version === 'h2'
      return e.cognitive_stage === expStageFilter
    })
  }, [explanations, expRuleFilter, expStageFilter, expModelFilter])

  const loading = insightsQ.isLoading || rulesQ.isLoading
  const error = insightsQ.error ?? rulesQ.error

  return (
    <div className="ins-stack">
      {/* Reusable crisp CAD 1px SVG diagonal hatch pattern for untested n/a matrix cells */}
      <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden>
        <defs>
          <pattern id="ins-na-hatch" width={6} height={6} patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1={0} y1={0} x2={0} y2={6} stroke="var(--line-strong)" strokeWidth={1} />
          </pattern>
        </defs>
      </svg>

      <PageHeader
        title="Insights & Rule Discovery"
        sub="Mechanic discovery matrix, judge-verified failure explanations, and direct replay / take-over entry points."
        actions={
          <div className="page-actions">
            <Link to="/leaderboard">
              <Button mono>← h1 Board</Button>
            </Link>
            <Link to="/leaderboard?view=h2">
              <Button mono>h2 Lab Board</Button>
            </Link>
            <Link to="/leaderboard?view=bench">
              <Button mono>Post-Training</Button>
            </Link>
            <Link to="/replay">
              <Button mono>Browse Replays</Button>
            </Link>
          </div>
        }
      />

      {loading ? (
        <Loading what="Loading rule diagnostics and insights" />
      ) : error ? (
        <ErrorState
          error={error}
          retry={() => {
            insightsQ.refetch()
            rulesQ.refetch()
          }}
        />
      ) : (
        <>
          <div className="ins-kpi-grid" aria-label="Diagnostic summary">
            <div className="ins-kpi-cell">
              <Stat
                label="Headline Findings"
                value={insights.length}
                sub="Every claim pinned to #runId · @step"
              />
            </div>
            <div className="ins-kpi-cell">
              <Stat
                label="Mechanics Tracked"
                value={rulesQ.data?.rules?.length ?? matrixGrid.rulesOrder.length}
                unit="rules"
                sub={`${cells.length} player × rule cells`}
              />
            </div>
            <div className="ins-kpi-cell">
              <Stat
                label="Failure Diagnoses"
                value={explanations.length}
                unit="levels"
                sub={explanationsQ.data?.judge_model ? `auditor: ${explanationsQ.data.judge_model}` : 'per-level root cause'}
              />
            </div>
            <div className="ins-kpi-cell">
              <Stat
                label="Failure Events"
                value={totalFailureEvents}
                unit="events"
                sub={`${failureModes.length} failure modes`}
              />
            </div>
          </div>

          {/* 8-col Square-Cell Rule × Player Matrix + 4-col Sticky Cell Inspector (fits 1080p above the fold) */}
          <Panel
            label="Rule × Player Discovery Matrix · Click Any Cell to Inspect"
            actions={
              <Button
                mono
                active={matrixMode === 'table'}
                onClick={() => setMatrixMode((m) => (m === 'plot' ? 'table' : 'plot'))}
              >
                {matrixMode === 'plot' ? 'Show Table' : 'Show Matrix'}
              </Button>
            }
          >
            <div className="ins-controls">
              <div className="ins-metric-pills">
                {(Object.keys(METRIC_META) as MatrixMetric[]).map((m) => (
                  <Button
                    key={m}
                    mono
                    active={metric === m}
                    onClick={() => setMetric(m)}
                  >
                    {METRIC_META[m].short}
                  </Button>
                ))}
              </div>
              <div className="ins-matrix-legend mono muted">
                <span className="ins-legend-swatch ins-legend-low" /> low
                <span className="ins-legend-swatch ins-legend-high" /> high
                <svg width={12} height={12} className="ins-legend-hatch" aria-hidden>
                  <rect width={12} height={12} fill="url(#ins-na-hatch)" stroke="var(--line-strong)" />
                </svg>{' '}
                n/a (untested)
              </div>
            </div>

            {!cells.length ? (
              <Empty>No rule-discovery cells available yet.</Empty>
            ) : (
              <div className="ins-matrix-split">
                <div className="ins-matrix-main">
                  {matrixMode === 'table' ? (
                    <div className="table-wrap">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Rule</th>
                            <th>Player</th>
                            <th className="num">Intro Lvls</th>
                            <th className="num">Intro Solve</th>
                            <th className="num">First Use</th>
                            <th className="num">Wasted Act</th>
                            <th className="num">Hyp Match</th>
                            <th className="num">Recomb Lvls</th>
                            <th className="num">Recomb Solve</th>
                          </tr>
                        </thead>
                        <tbody>
                          {cells.map((c) => {
                            const isSel =
                              activeCell?.rule === c.rule && cellLabel(activeCell) === cellLabel(c)
                            return (
                              <tr
                                key={`${c.rule}-${c.player_id}-${c.effort ?? 'none'}`}
                                className={cx('row-link', isSel && 'ins-row-selected')}
                                onClick={() => setSelectedCell(c)}
                              >
                                <td className="mono">
                                  <span className="ins-rule-label">
                                    <RuleSprite rule={c.rule} size={18} />
                                    {c.rule}
                                  </span>
                                </td>
                                <td className="mono">{cellLabel(c)}</td>
                                <td className="num">{c.intro_levels}</td>
                                <td className="num">
                                  {c.intro_levels > 0 ? `${(c.intro_solve_rate * 100).toFixed(0)}%` : 'n/a'}
                                </td>
                                <td className="num">{formatMetric(c.actions_to_first_use, 'actions_to_first_use')}</td>
                                <td className="num">{formatMetric(c.wasted_actions, 'wasted_actions')}</td>
                                <td className="num">{formatMetric(c.hypothesis_match_rate, 'hypothesis_match_rate')}</td>
                                <td className="num">{c.recombined_levels ?? 0}</td>
                                <td className="num">{formatMetric(c.recombined_solve_rate, 'recombined_solve_rate')}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="ins-square-wrap">
                      <table className="ins-square-matrix mono" role="grid" aria-label={METRIC_META[metric].label}>
                        <thead>
                          <tr>
                            <th className="ins-matrix-corner">rule \ player</th>
                            {matrixGrid.playersOrder.map((p) => (
                              <th key={p} className="ins-matrix-colhead" title={p}>
                                <span>{shortPlayerHeader(p)}</span>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {matrixGrid.rulesOrder.map((r) => (
                            <tr key={r}>
                              <th scope="row" className="ins-matrix-rowhead">
                                <span className="ins-rule-label">
                                  <RuleSprite rule={r} size={18} />
                                  <span>{r}</span>
                                </span>
                              </th>
                              {matrixGrid.playersOrder.map((p) => {
                                const c = matrixGrid.lookup.get(`${r}::${p}`) ?? null
                                const val = c ? cellMetricValue(c, metric) : null
                                const isSel =
                                  !!c && activeCell?.rule === c.rule && cellLabel(activeCell) === cellLabel(c)

                                if (val == null || !c) {
                                  return (
                                    <td
                                      key={p}
                                      className={cx('ins-sq-cell', 'ins-sq-na', isSel && 'ins-sq-selected')}
                                      onClick={() => c && setSelectedCell(c)}
                                      title={`${r} × ${p}: n/a (0 isolated levels)`}
                                    >
                                      <svg width="100%" height="100%" className="ins-na-bg" aria-hidden>
                                        <rect width="100%" height="100%" fill="url(#ins-na-hatch)" />
                                      </svg>
                                      <span className="ins-sq-na-label">—</span>
                                    </td>
                                  )
                                }

                                const rawT = (val - matrixGrid.minVal) / Math.max(1e-6, matrixGrid.maxVal - matrixGrid.minVal)
                                const norm = Math.max(0, Math.min(1, METRIC_META[metric].higherBetter ? rawT : 1 - rawT))
                                const mixPct = Math.round(norm * 100)
                                const textDark = mixPct >= 62

                                return (
                                  <td
                                    key={p}
                                    className={cx('ins-sq-cell', isSel && 'ins-sq-selected')}
                                    style={{
                                      background: `color-mix(in srgb, var(--seq-high) ${mixPct}%, var(--seq-low))`,
                                      color: textDark ? '#0e0e0f' : '#efefec',
                                    }}
                                    onClick={() => setSelectedCell(c)}
                                    title={`${r} × ${p}\n${METRIC_META[metric].label}: ${formatMetric(val, metric)}\nIntro: ${c.intro_levels} lvls · Recomb: ${c.recombined_levels ?? 0} lvls`}
                                  >
                                    {formatMetric(val, metric)}
                                  </td>
                                )
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* 4-col Sticky Cell Inspector */}
                <aside className="ins-inspector">
                  {activeCell ? (
                    <div className="ins-inspector-box">
                      <div className="ins-inspector-head">
                        <span className="kicker">cell inspector</span>
                        <span className="mono ins-inspector-title">
                          {activeCell.rule} × {cellLabel(activeCell)}
                        </span>
                      </div>
                      <RuleSprite rule={activeCell.rule} mode="strip" />
                      <dl className="ins-inspector-dl mono">
                        <dt>Intro solve</dt>
                        <dd>
                          {activeCell.intro_levels > 0
                            ? `${(activeCell.intro_solve_rate * 100).toFixed(0)}% (${activeCell.intro_levels} lvls)`
                            : 'n/a (0 intro lvls)'}
                        </dd>
                        <dt>Recomb solve</dt>
                        <dd>
                          {formatMetric(activeCell.recombined_solve_rate, 'recombined_solve_rate')} (
                          {activeCell.recombined_levels ?? 0} lvls)
                        </dd>
                        <dt>First rule use</dt>
                        <dd>{formatMetric(activeCell.actions_to_first_use, 'actions_to_first_use')} moves</dd>
                        <dt>Wasted moves</dt>
                        <dd>{formatMetric(activeCell.wasted_actions, 'wasted_actions')}</dd>
                        <dt>Hyp match</dt>
                        <dd>{formatMetric(activeCell.hypothesis_match_rate, 'hypothesis_match_rate')}</dd>
                        <dt>No-effect</dt>
                        <dd>{formatMetric(activeCell.repeated_no_effect_actions, 'repeated_no_effect_actions')}</dd>
                      </dl>

                      {cellExplanations.length > 0 && (
                        <div className="ins-inspector-exps">
                          <span className="kicker">matching failure diagnoses</span>
                          {cellExplanations.map((ex) => {
                            const replayHref = `/replay/${encodeURIComponent(ex.run_id)}${ex.step != null ? `?step=${ex.step}` : ''}`
                            const tkHref = buildTakeoverHref(ex.run_id, ex.step, ex.level, ex.game_id, ex.player_id)
                            return (
                              <div key={`${ex.run_id}-${ex.level}`} className="ins-mini-exp">
                                <div className="ins-mini-exp-top mono">
                                  <Chip outcome="GAME_OVER">{ex.verdict}</Chip>
                                  <Link to={replayHref} className="ins-pill" title={ex.run_id}>
                                    #{shortRunId(ex.run_id)} · @{ex.step ?? 0} →
                                  </Link>
                                  {tkHref && (
                                    <Link to={tkHref} className="ins-takeover-pill">
                                      [ TAKE OVER L{ex.level} ]
                                    </Link>
                                  )}
                                </div>
                                {ex.explanation && <p className="ins-mini-exp-text">{ex.explanation}</p>}
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  ) : (
                    <Empty>Select a cell in the matrix to inspect mechanic telemetry.</Empty>
                  )}
                </aside>
              </div>
            )}
          </Panel>

          {/* Claim-checked Findings */}
          <Panel label="Claim-Checked Findings (Direct Replay Evidence)">
            {!insights.length ? (
              <Empty>No synthesized insights available yet.</Empty>
            ) : (
              <div className="ins-findings-grid">
                {insights.map((ins) => (
                  <Panel
                    key={ins.id}
                    label={`${ins.category ?? 'finding'} · ${ins.id}`}
                    actions={
                      <Chip outcome={SEVERITY_OUTCOME[ins.severity ?? 'info'] ?? 'ABORTED'}>
                        {(ins.severity ?? 'info').toUpperCase()}
                      </Chip>
                    }
                  >
                    <div className="ins-card-body">
                      <h3>{ins.title}</h3>
                      <p className="ins-summary">{ins.summary}</p>
                      <div className="ins-evidence-list">
                        {ins.evidence.map((ev, i) => {
                          const displayVal =
                            typeof ev.value === 'number'
                              ? Number.isInteger(ev.value)
                                ? String(ev.value)
                                : ev.value.toFixed(4).replace(/\.?0+$/, '')
                              : String(ev.value)
                          const replayHref = ev.run_id
                            ? `/replay/${encodeURIComponent(ev.run_id)}${ev.step != null ? `?step=${ev.step}` : ''}`
                            : null
                          const tkHref = ev.run_id ? buildTakeoverHref(ev.run_id, ev.step, null) : null

                          return replayHref && ev.run_id ? (
                            <span key={`${ev.label}-${i}`} className="ins-evidence-group">
                              <Link className="ins-evidence-chip" to={replayHref} title={ev.run_id}>
                                <span className="muted">{ev.label}:</span>
                                <strong>{displayVal}</strong>
                                <span className="ins-evidence-link">
                                  #{shortRunId(ev.run_id)}
                                  {ev.step != null ? ` · @${ev.step}` : ''} →
                                </span>
                              </Link>
                              {tkHref && ev.step != null && (
                                <Link className="ins-takeover-pill mono" to={tkHref} title="Take over this run on /play">
                                  [ TAKE OVER @{ev.step} ]
                                </Link>
                              )}
                            </span>
                          ) : (
                            <span key={`${ev.label}-${i}`} className="ins-evidence-chip">
                              <span className="muted">{ev.label}:</span>
                              <strong>{displayVal}</strong>
                            </span>
                          )
                        })}
                      </div>
                    </div>
                  </Panel>
                ))}
              </div>
            )}
          </Panel>

          <div className="ins-two-col">
            <Panel
              label="Cross-Level Curriculum Learning Curve (L1 → L6)"
              actions={
                learningCurve.length > 0 && (
                  <Button
                    mono
                    active={curveMode === 'table'}
                    onClick={() => setCurveMode((m) => (m === 'plot' ? 'table' : 'plot'))}
                  >
                    {curveMode === 'plot' ? 'Show Table' : 'Show Plot'}
                  </Button>
                )
              }
            >
              {!learningCurve.length ? (
                <Empty>No per-level progression curve recorded yet.</Empty>
              ) : curveMode === 'table' ? (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th className="num">Level</th>
                        <th>Player</th>
                        <th className="num">Attempts</th>
                        <th className="num">Solve Rate</th>
                        <th className="num">Mean Eff. Score</th>
                        <th className="num">Mean Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {learningCurve.map((pt) => (
                        <tr key={`${pt.level}-${pt.player_id}`}>
                          <td className="num">L{pt.level}</td>
                          <td className="mono">{pt.player_id}</td>
                          <td className="num">{pt.attempts}</td>
                          <td className="num">{(pt.solve_rate * 100).toFixed(0)}%</td>
                          <td className="num">{pt.mean_score.toFixed(3)}</td>
                          <td className="num">{pt.mean_actions != null ? pt.mean_actions.toFixed(1) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <PlotFigure
                  deps={[curvePlayers]}
                  make={(width) => ({
                    width,
                    height: 250,
                    marginBottom: 38,
                    x: { label: 'Curriculum level (1 = intro … 6 = full recombination)', tickFormat: (d: number) => `L${d}` },
                    y: { domain: [0, 1.04], label: 'Mean efficiency score' },
                    color: { legend: true, range: seriesColors() },
                    marks: [
                      Plot.ruleY([1.0], {
                        stroke: cssVar('--text-2'),
                      }),
                      Plot.lineY(curvePlayers, {
                        x: 'level',
                        y: 'mean_score',
                        stroke: 'player_id',
                        strokeWidth: 2,
                      }),
                      Plot.dot(curvePlayers, {
                        x: 'level',
                        y: 'mean_score',
                        fill: 'player_id',
                        stroke: cssVar('--surface-1'),
                        strokeWidth: 1.5,
                        r: 5,
                        tip: true,
                      }),
                    ],
                  })}
                />
              )}
            </Panel>

            <Panel label="Failure Taxonomy & Take-Over Clips">
              {!failureModes.length ? (
                <Empty>Zero failure events detected across loaded runs.</Empty>
              ) : (
                <div className="ins-failure-list">
                  {failureModes.map((fm) => {
                    const sharePct = totalFailureEvents > 0 ? Math.round((fm.count / totalFailureEvents) * 100) : 0
                    const barPct = Math.max(2, Math.round((fm.count / maxFailureCount) * 100))
                    const isWarn = fm.mode === 'budget_exhaustion' || fm.mode === 'late_reset'
                    return (
                      <div key={fm.mode} className="ins-failure-block">
                        <div className="ins-failure-head">
                          <span className="mono">
                            <strong>{fm.mode}</strong>{' '}
                            <span className="muted">({sharePct}%)</span>
                          </span>
                          <Chip outcome={isWarn ? 'BUDGET' : 'GAME_OVER'}>
                            {fm.count} events
                          </Chip>
                        </div>
                        <div className="ins-failure-bar-track" aria-hidden="true">
                          <div
                            className="ins-failure-bar-fill"
                            style={{
                              width: `${barPct}%`,
                              background: isWarn ? 'var(--warn)' : 'var(--bad)',
                            }}
                          />
                        </div>
                        <div className="ins-evidence-list">
                          {fm.examples.slice(0, 4).map((ex, idx) => {
                            if (!ex.run_id) return null
                            const href = `/replay/${encodeURIComponent(ex.run_id)}${ex.step != null ? `?step=${ex.step}` : ''}`
                            const tkHref = buildTakeoverHref(ex.run_id, ex.step, ex.level, null, ex.player_id)
                            return (
                              <span key={`${fm.mode}-${idx}`} className="ins-evidence-group">
                                <Link className="ins-evidence-chip" to={href} title={ex.run_id}>
                                  <span>{ex.player_id ? shortPlayerHeader(ex.player_id) : 'run'}</span>
                                  {ex.level != null && <span className="muted">L{ex.level}</span>}
                                  <span className="ins-evidence-link">
                                    #{shortRunId(ex.run_id)}
                                    {ex.step != null ? ` · @${ex.step}` : ''} →
                                  </span>
                                </Link>
                                {tkHref && (
                                  <Link className="ins-takeover-pill mono" to={tkHref}>
                                    [ TAKE OVER{ex.step != null ? ` @${ex.step}` : ''} ]
                                  </Link>
                                )}
                              </span>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Panel>
          </div>

          {/* Truth-Diffed Reasoning Forensics: 5-Stage Cognitive Funnel & Knowing–Doing Gap */}
          {expSummary && expSummary.by_cognitive_stage?.length > 0 && (
            <Panel
              label="Truth-Diffed Reasoning Forensics · Cognitive Bottleneck Funnel (h1 vs h2)"
              actions={
                <span className="mono ins-kd-headline">
                  Knowing–Doing Gap: <strong>{(expSummary.knowing_doing_gap_rate * 100).toFixed(0)}%</strong>{' '}
                  <span className="muted">
                    ({expSummary.knowing_doing_gap_count}/{expSummary.non_tier0_failed_levels} hidden-rule failures deduced rule in CoT/notes)
                  </span>
                </span>
              }
            >
              <div className="ins-forensic-split">
                <div className="ins-funnel-col">
                  <div className="ins-funnel-legend mono muted">
                    <span>Click any cognitive stage to filter diagnoses below</span>
                    <span>
                      <i className="ins-swatch-h1" /> h1 ({expSummary.by_harness.h1?.total ?? 0}) ·{' '}
                      <i className="ins-swatch-h2" /> h2 ({expSummary.by_harness.h2?.total ?? 0})
                    </span>
                  </div>
                  <div className="ins-funnel-list">
                    {expSummary.by_cognitive_stage.map((stg) => {
                      const active = expStageFilter === stg.stage
                      const h1Pct = Math.round(stg.h1_share * 100)
                      const h2Pct = Math.round(stg.h2_share * 100)
                      return (
                        <button
                          type="button"
                          key={stg.stage}
                          className={cx('ins-funnel-row', active && 'ins-funnel-row-active')}
                          onClick={() => setExpStageFilter((cur) => (cur === stg.stage ? 'all' : stg.stage))}
                        >
                          <div className="ins-funnel-row-top mono">
                            <span>
                              <strong>{stg.label}</strong>
                              {stg.top_root_cause && <span className="muted"> · {stg.top_root_cause}</span>}
                            </span>
                            <span>
                              <strong>{stg.count}</strong>{' '}
                              <span className="muted">({Math.round(stg.share * 100)}%)</span>
                            </span>
                          </div>
                          <div className="ins-funnel-bars">
                            <div className="ins-funnel-bar-line mono">
                              <span className="muted">h1</span>
                              <div className="ins-failure-bar-track">
                                <div
                                  className="ins-failure-bar-fill"
                                  style={{ width: `${Math.max(stg.h1_count ? 2 : 0, h1Pct)}%`, background: 'var(--text-2)' }}
                                />
                              </div>
                              <span className="num muted">{h1Pct}%</span>
                            </div>
                            <div className="ins-funnel-bar-line mono">
                              <span className="ins-h2-tag">h2</span>
                              <div className="ins-failure-bar-track">
                                <div
                                  className="ins-failure-bar-fill"
                                  style={{ width: `${Math.max(stg.h2_count ? 2 : 0, h2Pct)}%`, background: 'var(--accent)' }}
                                />
                              </div>
                              <span className="num ins-h2-tag">{h2Pct}%</span>
                            </div>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="ins-model-forensic-col">
                  <div className="ins-kd-callout">
                    <div className="ins-kd-callout-head mono">
                      <strong>THE KNOWING–DOING GAP</strong>
                      <Button
                        mono
                        active={expStageFilter === 'knowing_doing'}
                        onClick={() => setExpStageFilter((cur) => (cur === 'knowing_doing' ? 'all' : 'knowing_doing'))}
                      >
                        {expStageFilter === 'knowing_doing' ? 'Showing Gap Cases' : `Filter ${expSummary.knowing_doing_gap_count} Cases`}
                      </Button>
                    </div>
                    <p className="ins-kd-callout-body">
                      By diffing per-step <span className="mono">reasoning</span>/<span className="mono">hypothesis</span> against hidden engine{' '}
                      <span className="mono">truth</span>, <strong>{(expSummary.knowing_doing_gap_rate * 100).toFixed(1)}%</strong> of failed
                      non-Tier-0 levels explicitly articulated the active mechanic before failing multi-step execution. Upgrading{' '}
                      <span className="mono">h1 → h2</span> eliminates Stage 1 perception failures (
                      <span className="mono">
                        {Math.round(((expSummary.by_cognitive_stage[0]?.h1_share ?? 0) * 100))}% →{' '}
                        {Math.round(((expSummary.by_cognitive_stage[0]?.h2_share ?? 0) * 100))}%
                      </span>
                      ), concentrating residual failures in rule induction and spatial rollout.
                    </p>
                    <div className="ins-source-strip mono muted">
                      <span>CoT traces: {expSummary.by_reasoning_source.cot ?? 0}</span>
                      <span>· h1 notes: {expSummary.by_reasoning_source.notes ?? 0}</span>
                      <span>· hyp-only (encrypted CoT): {expSummary.by_reasoning_source.hypothesis_only ?? 0}</span>
                    </div>
                  </div>

                  <div className="table-wrap ins-forensic-table-wrap">
                    <table className="table ins-forensic-table">
                      <thead>
                        <tr>
                          <th>Model</th>
                          <th>Hrn</th>
                          <th>Src</th>
                          <th className="num">Fail</th>
                          <th className="num">Knew Rule</th>
                          <th>Primary Bottleneck</th>
                        </tr>
                      </thead>
                      <tbody>
                        {expSummary.by_model.slice(0, 8).map((m) => {
                          const key = `${m.player_id}::${m.harness_version}`
                          const active = expModelFilter === key
                          return (
                            <tr
                              key={key}
                              className={cx('ins-clickable-row', active && 'ins-row-selected')}
                              onClick={() => setExpModelFilter((cur) => (cur === key ? 'all' : key))}
                            >
                              <td className="mono">{shortPlayerHeader(m.player_id)}</td>
                              <td className="mono">
                                <span className={m.harness_version === 'h2' ? 'ins-h2-tag' : 'muted'}>{m.harness_version}</span>
                              </td>
                              <td className="mono muted">{m.reasoning_source === 'hypothesis_only' ? 'hyp-only' : m.reasoning_source}</td>
                              <td className="num">{m.total}</td>
                              <td className="num">{(m.knowing_doing_gap_rate * 100).toFixed(0)}%</td>
                              <td className="mono">{m.primary_bottleneck}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </Panel>
          )}

          {/* Judge / Truth-Diffed Failure Explanations Ledger (`explanations.json`) */}
          {explanations.length > 0 && (
            <Panel
              label={`Why Models Failed · ${filteredExplanations.length} Level Diagnoses`}
              actions={
                <div className="ins-ledger-head-actions mono">
                  {(expStageFilter !== 'all' || expRuleFilter !== 'all' || expModelFilter !== 'all') && (
                    <Button
                      mono
                      onClick={() => {
                        setExpStageFilter('all')
                        setExpRuleFilter('all')
                        setExpModelFilter('all')
                      }}
                    >
                      Reset Filters
                    </Button>
                  )}
                  <span className="muted">auditor: {explanationsQ.data?.judge_model ?? 'reasoning-auditor-v2'}</span>
                </div>
              }
            >
              <div className="ins-controls ins-forensic-filters">
                <div className="ins-metric-pills">
                  {[
                    { id: 'all', label: 'all stages' },
                    { id: 'knowing_doing', label: 'knew rule in CoT' },
                    { id: 'h2', label: 'h2 only' },
                    { id: 'perception', label: '1·perception' },
                    { id: 'rule_induction', label: '2·induction' },
                    { id: 'belief_updating', label: '3·updating' },
                    { id: 'spatial_planning', label: '4·spatial' },
                    { id: 'budget_management', label: '5·budget' },
                  ].map((f) => (
                    <Button key={f.id} mono active={expStageFilter === f.id} onClick={() => setExpStageFilter(f.id)}>
                      {f.label}
                    </Button>
                  ))}
                </div>
                <div className="ins-metric-pills">
                  {explanationRules.map((r) => (
                    <Button key={r} mono active={expRuleFilter === r} onClick={() => setExpRuleFilter(r)}>
                      {r}
                    </Button>
                  ))}
                </div>
              </div>
              {!filteredExplanations.length ? (
                <Empty>No level diagnoses match the active stage/mechanic filter.</Empty>
              ) : (
                <div className="ins-exp-grid">
                  {filteredExplanations.slice(0, 12).map((ex) => {
                    const replayHref = `/replay/${encodeURIComponent(ex.run_id)}?step=${ex.step ?? 0}&xray=50`
                    const tkHref = buildTakeoverHref(ex.run_id, ex.step, ex.level, ex.game_id, ex.player_id)
                    const srcLabel =
                      ex.reasoning_source === 'cot'
                        ? 'h2 CoT'
                        : ex.reasoning_source === 'hypothesis_only'
                          ? 'hyp-only (encrypted CoT)'
                          : 'h1 notes'
                    const quoteFrom =
                      ex.quote_source === 'reasoning'
                        ? ex.harness_version === 'h2'
                          ? '<think> CoT'
                          : 'scratchpad notes'
                        : 'hypothesis'
                    return (
                      <div key={`${ex.run_id}-${ex.level}`} className="ins-exp-card">
                        <div className="ins-exp-card-head mono">
                          <span className="ins-rule-label">
                            {ex.rule && <RuleSprite rule={ex.rule} size={18} />}
                            <strong>{ex.player_id ?? 'model'}</strong>
                            {ex.harness_version && (
                              <span className={cx('ins-hrn-badge', ex.harness_version === 'h2' && 'ins-hrn-h2')}>
                                {ex.harness_version}
                              </span>
                            )}
                            <span className="muted">· L{ex.level}</span>
                            {ex.rule && <span className="secondary">· {ex.rule}</span>}
                          </span>
                          <Chip outcome={ex.cognitive_stage === 'spatial_planning' || ex.cognitive_stage === 'budget_management' ? 'BUDGET' : 'GAME_OVER'}>
                            {ex.cognitive_stage ?? ex.verdict}
                          </Chip>
                        </div>

                        <div className="ins-exp-submeta mono">
                          <span className="muted">cause: {ex.root_cause ?? ex.verdict}</span>
                          <span className="muted">· trace: {srcLabel}</span>
                          {ex.deduced_rule_in_cot && (
                            <span className="ins-kd-badge">
                              KNEW RULE{ex.deduced_rule_step != null ? ` @${ex.deduced_rule_step}` : ''}
                            </span>
                          )}
                        </div>

                        {ex.truth_contrast && (
                          <div className="ins-truth-contrast">
                            <span className="mono ins-truth-kicker">TRUTH DIFF</span> {ex.truth_contrast}
                          </div>
                        )}

                        {ex.explanation && <p className="ins-exp-card-text">{ex.explanation}</p>}
                        {ex.evidence_quote && (
                          <blockquote className="ins-exp-card-quote mono">
                            <span className="ins-quote-kicker">verbatim ({quoteFrom}):</span> “{ex.evidence_quote}”
                          </blockquote>
                        )}
                        <div className="ins-exp-card-foot mono">
                          <Link to={replayHref} className="ins-pill" title="Open divergence frame with 50% X-Ray truth curtain">
                            [ X-RAY DIVERGENCE @{ex.step ?? 0} · #{shortRunId(ex.run_id)} ] →
                          </Link>
                          {tkHref && (
                            <Link to={tkHref} className="ins-takeover-pill">
                              [ TAKE OVER @{ex.step ?? 1} ]
                            </Link>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Panel>
          )}
        </>
      )}
    </div>
  )
}
