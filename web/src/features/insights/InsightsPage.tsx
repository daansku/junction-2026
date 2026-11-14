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
  { label: string; isRate?: boolean; introOnly?: boolean; higherBetter: boolean }
> = {
  recombined_solve_rate: {
    label: 'Recombined solve rate',
    isRate: true,
    higherBetter: true,
  },
  intro_solve_rate: {
    label: 'Intro solve rate',
    isRate: true,
    introOnly: true,
    higherBetter: true,
  },
  actions_to_first_use: {
    label: 'Actions to first rule use',
    introOnly: true,
    higherBetter: false,
  },
  wasted_actions: {
    label: 'Wasted actions (vs optimal)',
    introOnly: true,
    higherBetter: false,
  },
  hypothesis_match_rate: {
    label: 'Hypothesis match rate',
    isRate: true,
    introOnly: true,
    higherBetter: true,
  },
  repeated_no_effect_actions: {
    label: 'No-effect loop actions',
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

export function InsightsPage() {
  const insightsQ = useQuery({
    queryKey: ['derived', 'insights'],
    queryFn: () => api.derived<InsightsDocument>('insights'),
  })
  const rulesQ = useQuery({
    queryKey: ['derived', 'rules'],
    queryFn: () => api.derived<RulesDocument>('rules'),
  })

  const [metric, setMetric] = useState<MatrixMetric>('recombined_solve_rate')
  const [matrixMode, setMatrixMode] = useState<'plot' | 'table'>('plot')
  const [curveMode, setCurveMode] = useState<'plot' | 'table'>('plot')
  const [selectedCell, setSelectedCell] = useState<RuleCell | null>(null)

  const insights = insightsQ.data?.insights ?? []
  const cells = rulesQ.data?.cells ?? []
  const learningCurve = rulesQ.data?.level_learning_curve ?? []
  const failureModes = rulesQ.data?.failure_modes ?? []

  const totalFailureEvents = useMemo(
    () => failureModes.reduce((acc, f) => acc + f.count, 0),
    [failureModes],
  )

  const heatPoints = useMemo(() => {
    const list: Array<{
      rule: string
      player: string
      value: number
      label: string
      cell: RuleCell
    }> = []
    for (const c of cells) {
      const v = cellMetricValue(c, metric)
      if (v == null) continue
      list.push({
        rule: c.rule,
        player: cellLabel(c),
        value: v,
        label: formatMetric(v, metric),
        cell: c,
      })
    }
    return list
  }, [cells, metric])

  const curvePlayers = useMemo(() => {
    const unique = Array.from(new Set(learningCurve.map((p) => p.player_id)))
    if (unique.length <= 4) return learningCurve
    // Fold beyond top 4 categorical series per DESIGN.md §3
    const keep = new Set(unique.slice(0, 4))
    return learningCurve.filter((p) => keep.has(p.player_id))
  }, [learningCurve])

  const activeCell = selectedCell ?? cells.find((c) => c.intro_levels > 0) ?? cells[0] ?? null

  const loading = insightsQ.isLoading || rulesQ.isLoading
  const error = insightsQ.error ?? rulesQ.error

  return (
    <div className="ins-stack">
      <PageHeader
        title="Insights & Rule Discovery"
        sub="How quickly agents discover hidden mechanics, where budgets collapse, and deep-links to exact replay steps."
        actions={
          <div className="page-actions">
            <Link to="/leaderboard">
              <Button mono>← Leaderboard</Button>
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
                sub="Every claim pinned to run_id + step"
              />
            </div>
            <div className="ins-kpi-cell">
              <Stat
                label="Mechanics Tracked"
                value={rulesQ.data?.rules?.length ?? new Set(cells.map((c) => c.rule)).size}
                unit="rules"
                sub={`${cells.length} player × rule cells evaluated`}
              />
            </div>
            <div className="ins-kpi-cell">
              <Stat
                label="Failure Events"
                value={totalFailureEvents}
                unit="events"
                sub={`${failureModes.length} failure categories logged`}
              />
            </div>
            <div className="ins-kpi-cell">
              <Stat
                label="Auto-Proposal Loop"
                value="eval-v2"
                sub="Bottom intro-rate & waste signals feed rule proposals"
              />
            </div>
          </div>

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

                          return replayHref ? (
                            <Link key={`${ev.label}-${i}`} className="ins-evidence-chip" to={replayHref}>
                              <span className="muted">{ev.label}:</span>
                              <strong>{displayVal}</strong>
                              <span className="ins-evidence-link">
                                {ev.run_id}
                                {ev.step != null ? ` @step ${ev.step}` : ''} →
                              </span>
                            </Link>
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

          <Panel
            label="Rule × Player Discovery Matrix"
            actions={
              <Button
                mono
                active={matrixMode === 'table'}
                onClick={() => setMatrixMode((m) => (m === 'plot' ? 'table' : 'plot'))}
              >
                {matrixMode === 'plot' ? 'Show Table' : 'Show Heatmap'}
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
                    {METRIC_META[m].label}
                  </Button>
                ))}
              </div>
            </div>

            {!cells.length ? (
              <Empty>No rule-discovery cells available yet.</Empty>
            ) : matrixMode === 'table' || heatPoints.length === 0 ? (
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
                        activeCell?.rule === c.rule && activeCell?.player_id === c.player_id
                      return (
                        <tr
                          key={`${c.rule}-${c.player_id}-${c.effort ?? 'none'}`}
                          className={cx('row-link', isSel && 'ins-row-selected')}
                          onClick={() => setSelectedCell(c)}
                        >
                          <td className="mono">{c.rule}</td>
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
              <PlotFigure
                deps={[heatPoints, metric]}
                make={(width) => ({
                  width,
                  height: Math.max(200, new Set(heatPoints.map((d) => d.rule)).size * 44 + 80),
                  marginLeft: 112,
                  marginBottom: 42,
                  padding: 0.08,
                  x: { label: 'Player', axis: 'bottom' },
                  y: { label: 'Rule' },
                  color: {
                    type: 'linear',
                    range: [cssVar('--seq-low'), cssVar('--seq-high')],
                    domain: METRIC_META[metric].isRate ? [0, 1] : undefined,
                    legend: true,
                    label: METRIC_META[metric].label,
                  },
                  marks: [
                    Plot.cell(heatPoints, {
                      x: 'player',
                      y: 'rule',
                      fill: 'value',
                      inset: 1,
                      tip: true,
                      title: (d: (typeof heatPoints)[number]) =>
                        `${d.rule} × ${d.player}\n${METRIC_META[metric].label}: ${d.label}\nIntro lvls: ${d.cell.intro_levels} · Recombined lvls: ${d.cell.recombined_levels ?? 0}`,
                    }),
                    Plot.text(heatPoints, {
                      x: 'player',
                      y: 'rule',
                      text: 'label',
                      fill: cssVar('--text-1'),
                    }),
                  ],
                })}
              />
            )}

            {activeCell && (
              <div className="ins-detail-grid mono">
                <div className="ins-detail-item">
                  <span className="kicker">Selected Cell</span>
                  <span>
                    {activeCell.rule} × {cellLabel(activeCell)}
                  </span>
                </div>
                <div className="ins-detail-item">
                  <span className="kicker">Intro Performance</span>
                  <span>
                    {activeCell.intro_levels > 0
                      ? `${(activeCell.intro_solve_rate * 100).toFixed(0)}% solved (${activeCell.intro_levels} lvls)`
                      : 'Passive rule (0 isolated intro levels)'}
                  </span>
                </div>
                <div className="ins-detail-item">
                  <span className="kicker">Recombined Performance</span>
                  <span>
                    {formatMetric(activeCell.recombined_solve_rate, 'recombined_solve_rate')} across{' '}
                    {activeCell.recombined_levels ?? 0} levels
                  </span>
                </div>
                <div className="ins-detail-item">
                  <span className="kicker">Discovery Overhead</span>
                  <span>
                    first use {formatMetric(activeCell.actions_to_first_use, 'actions_to_first_use')} · wasted{' '}
                    {formatMetric(activeCell.wasted_actions, 'wasted_actions')}
                  </span>
                </div>
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
                    height: 260,
                    marginBottom: 38,
                    x: { label: 'Curriculum level (1 = intro … 6 = full recombination)', tickFormat: (d: number) => `L${d}` },
                    y: { domain: [0, 1.04], label: 'Mean efficiency score' },
                    color: { legend: true, range: seriesColors() },
                    marks: [
                      Plot.ruleY([1.0], {
                        stroke: cssVar('--text-2'),
                        strokeDasharray: '4,4',
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
                        r: 4,
                        tip: true,
                      }),
                    ],
                  })}
                />
              )}
            </Panel>

            <Panel label="Failure Taxonomy & Replay Entry Points">
              {!failureModes.length ? (
                <Empty>Zero failure events detected across loaded runs.</Empty>
              ) : (
                <div className="ins-failure-list">
                  {failureModes.map((fm) => (
                    <div key={fm.mode} className="ins-failure-block">
                      <div className="ins-failure-head">
                        <span className="mono">
                          <strong>{fm.mode}</strong>
                        </span>
                        <Chip outcome={fm.mode === 'budget_exhaustion' ? 'BUDGET' : 'GAME_OVER'}>
                          {fm.count} events
                        </Chip>
                      </div>
                      <div className="ins-evidence-list">
                        {fm.examples.slice(0, 4).map((ex, idx) => {
                          if (!ex.run_id) return null
                          const href = `/replay/${encodeURIComponent(ex.run_id)}${ex.step != null ? `?step=${ex.step}` : ''}`
                          return (
                            <Link key={`${fm.mode}-${idx}`} className="ins-evidence-chip" to={href}>
                              <span>{ex.player_id ?? 'run'}</span>
                              {ex.level != null && <span className="muted">L{ex.level}</span>}
                              {ex.actions != null && <span className="muted">{ex.actions} act</span>}
                              <span className="ins-evidence-link">
                                {ex.run_id}
                                {ex.step != null ? ` @${ex.step}` : ''} →
                              </span>
                            </Link>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}
