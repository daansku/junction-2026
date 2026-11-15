import * as Plot from '@observablehq/plot'
import { useMemo, useRef, useState } from 'react'
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
  cx,
} from '@/design/primitives'
import { api } from '@/lib/api'
import { PlotFigure, cssVar } from '@/lib/PlotFigure'
import { playerColor } from '@/lib/modelColors'
import type { RunMeta } from '@/lib/types'
import { fetchExplanations } from '@/features/play/epistemicApi'
import { RuleSprite } from '@/features/play/XrayOverlay'
import {
  conciseSummary,
  friendlyFailureMode,
  friendlyPlayer,
  friendlyRule,
  friendlyStageShort,
  friendlyStageTitle,
  truncateQuote,
} from './labels'
import type { RulesDocument } from './types'
import './insights.css'

export function InsightsPage() {
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

  const whyFailedRef = useRef<HTMLDivElement | null>(null)
  const [curveMode, setCurveMode] = useState<'plot' | 'table'>('plot')
  const [expRuleFilter, setExpRuleFilter] = useState<string>('all')
  const [expStageFilter, setExpStageFilter] = useState<string>('all')
  const [expModelFilter, setExpModelFilter] = useState<string>('all')
  const [visibleCount, setVisibleCount] = useState<number>(6)
  const [showAllRules, setShowAllRules] = useState<boolean>(false)

  const cells = rulesQ.data?.cells ?? []
  const learningCurve = rulesQ.data?.level_curve ?? rulesQ.data?.level_learning_curve ?? []
  const failureModes = rulesQ.data?.failure_modes ?? []
  const explanations = explanationsQ.data?.explanations ?? []
  const expSummary = explanationsQ.data?.summary ?? null

  const jumpToFailures = (opts: { stage?: string; rule?: string; model?: string }) => {
    if (opts.stage !== undefined) setExpStageFilter(opts.stage)
    if (opts.rule !== undefined) setExpRuleFilter(opts.rule)
    if (opts.model !== undefined) setExpModelFilter(opts.model)
    setVisibleCount(6)
    requestAnimationFrame(() => {
      whyFailedRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

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

  const curvePlayers = useMemo(() => {
    const nonTrivial = learningCurve.filter((p) => p.player_id !== 'noop' && p.player_id !== 'stop_early')
    const src = nonTrivial.length > 0 ? nonTrivial : learningCurve
    const unique = Array.from(new Set(src.map((p) => p.player_id)))
    let chosen = src
    if (unique.length > 4) {
      const scoreByPlayer = new Map<string, number>()
      const countByPlayer = new Map<string, number>()
      for (const pt of src) {
        scoreByPlayer.set(pt.player_id, (scoreByPlayer.get(pt.player_id) ?? 0) + pt.mean_score)
        countByPlayer.set(pt.player_id, (countByPlayer.get(pt.player_id) ?? 0) + 1)
      }
      const ranked = [...unique].sort((a, b) => {
        if (a === 'optimal') return -1
        if (b === 'optimal') return 1
        if (a === 'human') return -1
        if (b === 'human') return 1
        const ma = (scoreByPlayer.get(a) ?? 0) / Math.max(1, countByPlayer.get(a) ?? 1)
        const mb = (scoreByPlayer.get(b) ?? 0) / Math.max(1, countByPlayer.get(b) ?? 1)
        return mb - ma
      })
      const keep = new Set(ranked.slice(0, 4))
      chosen = src.filter((p) => keep.has(p.player_id))
    }
    return chosen.map((pt) => ({
      ...pt,
      playerLabel: friendlyPlayer(pt.player_id),
    }))
  }, [learningCurve])

  const ruleSummaryRows = useMemo(() => {
    const byRule = new Map<
      string,
      {
        rule: string
        aiSolvedWeight: number
        aiLevels: number
        humanSolvedWeight: number
        humanLevels: number
        failCases: number
      }
    >()

    const failCountByRule = new Map<string, number>()
    for (const ex of explanations) {
      if (ex.rule) failCountByRule.set(ex.rule, (failCountByRule.get(ex.rule) ?? 0) + 1)
    }

    for (const c of cells) {
      if (c.rule === 'goal' || c.rule === 'walls' || c.rule === 'move_budget') continue
      const isBase =
        c.player_id === 'optimal' ||
        c.player_id === 'noop' ||
        c.player_id === 'random' ||
        c.player_id === 'stop_early'
      if (isBase) continue

      let entry = byRule.get(c.rule)
      if (!entry) {
        entry = {
          rule: c.rule,
          aiSolvedWeight: 0,
          aiLevels: 0,
          humanSolvedWeight: 0,
          humanLevels: 0,
          failCases: failCountByRule.get(c.rule) ?? 0,
        }
        byRule.set(c.rule, entry)
      }

      const lvls = (c.intro_levels ?? 0) + (c.recombined_levels ?? 0)
      const rate =
        c.recombined_levels && c.recombined_solve_rate != null
          ? (c.intro_levels * c.intro_solve_rate + c.recombined_levels * c.recombined_solve_rate) /
            Math.max(1, lvls)
          : c.intro_solve_rate

      if (c.player_id === 'human') {
        if (lvls > 0) {
          entry.humanSolvedWeight += rate * lvls
          entry.humanLevels += lvls
        }
      } else if (lvls > 0) {
        entry.aiSolvedWeight += rate * lvls
        entry.aiLevels += lvls
      }
    }

    return Array.from(byRule.values())
      .filter((r) => r.aiLevels > 0 || r.failCases > 0)
      .map((r) => ({
        rule: r.rule,
        label: friendlyRule(r.rule),
        aiSolveRate: r.aiLevels > 0 ? r.aiSolvedWeight / r.aiLevels : null,
        humanSolveRate: r.humanLevels > 0 ? r.humanSolvedWeight / r.humanLevels : null,
        failCases: r.failCases,
      }))
      .sort((a, b) => (a.aiSolveRate ?? 1) - (b.aiSolveRate ?? 1) || b.failCases - a.failCases)
  }, [cells, explanations])

  const explanationRules = useMemo(
    () => Array.from(new Set(explanations.map((e) => e.rule).filter((r): r is string => !!r))).sort(),
    [explanations],
  )

  const filteredExplanations = useMemo(() => {
    return explanations.filter((e) => {
      if (expRuleFilter !== 'all' && e.rule !== expRuleFilter) return false
      if (expModelFilter !== 'all' && `${e.player_id ?? ''}::${e.harness_version ?? 'h1'}` !== expModelFilter)
        return false
      if (expStageFilter === 'all') return true
      if (expStageFilter === 'knowing_doing') return !!e.deduced_rule_in_cot
      if (expStageFilter === 'h2') return e.harness_version === 'h2'
      return e.cognitive_stage === expStageFilter
    })
  }, [explanations, expRuleFilter, expStageFilter, expModelFilter])

  const perceptionStage = expSummary?.by_cognitive_stage?.find((s) => s.stage === 'perception')
  const h1PerceptionPct = Math.round((perceptionStage?.h1_share ?? 0) * 100)
  const h2PerceptionPct = Math.round((perceptionStage?.h2_share ?? 0) * 100)
  const kdGapPct = expSummary ? Math.round(expSummary.knowing_doing_gap_rate * 100) : 0
  const hasFilters = expStageFilter !== 'all' || expRuleFilter !== 'all' || expModelFilter !== 'all'

  if (rulesQ.isLoading && explanationsQ.isLoading) {
    return <Loading what="Loading failure analysis" />
  }
  if (rulesQ.error) {
    return (
      <ErrorState
        error={rulesQ.error}
        retry={() => {
          rulesQ.refetch()
          explanationsQ.refetch()
        }}
      />
    )
  }

  return (
    <div className="ins-stack">
      <PageHeader
        title="Why Models Fail"
      />

      {/* 1. COMPACT FAILURE OVERVIEW — 3 big numbers + clickable breakdown (minimal text) */}
      {expSummary && (
        <Panel
          label="Failure Overview"
          actions={<span className="mono muted">click any metric to filter below</span>}
        >
          <div className="ins-stat-strip">
            <button
              type="button"
              className={cx('ins-stat-btn', expStageFilter === 'knowing_doing' && 'ins-stat-btn-active')}
              onClick={() =>
                jumpToFailures({ stage: expStageFilter === 'knowing_doing' ? 'all' : 'knowing_doing' })
              }
            >
              <span className="ins-stat-num ins-accent mono">{kdGapPct}%</span>
              <span className="ins-stat-title">Knew the rule, still failed</span>
              <span className="ins-stat-sub mono muted">
                {expSummary.knowing_doing_gap_count} of {expSummary.non_tier0_failed_levels} failed levels
              </span>
            </button>

            <button
              type="button"
              className={cx('ins-stat-btn', expStageFilter === 'h2' && 'ins-stat-btn-active')}
              onClick={() => jumpToFailures({ stage: expStageFilter === 'h2' ? 'all' : 'h2' })}
            >
              <span className="ins-stat-num mono">
                {h1PerceptionPct}% → {h2PerceptionPct}%
              </span>
              <span className="ins-stat-title">Misread the board, standard → extended</span>
              <span className="ins-stat-sub mono muted">Remembering earlier turns removes misreads</span>
            </button>

            <button
              type="button"
              className="ins-stat-btn"
              onClick={() => jumpToFailures({ stage: 'all', rule: 'all', model: 'all' })}
            >
              <span className="ins-stat-num mono">{explanations.length}</span>
              <span className="ins-stat-title">Audited failed levels</span>
              <span className="ins-stat-sub mono muted">Each one links to the moment it went wrong</span>
            </button>
          </div>

          {expSummary.by_cognitive_stage?.length > 0 && (
            <div className="ins-forensic-split">
              <div className="ins-funnel-col">
                <div className="ins-funnel-legend mono muted">
                  <span>Where attempts break</span>
                  <span>
                    <i className="ins-swatch-h1" /> standard ({expSummary.by_harness.h1?.total ?? 0}) ·{' '}
                    <i className="ins-swatch-h2" /> extended ({expSummary.by_harness.h2?.total ?? 0})
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
                        onClick={() => {
                          setExpStageFilter((cur) => (cur === stg.stage ? 'all' : stg.stage))
                          setVisibleCount(6)
                        }}
                      >
                        <div className="ins-funnel-row-top">
                          <span className="ins-stage-title">
                            {friendlyStageTitle(stg.stage, stg.label)}
                          </span>
                          <span className="mono ins-stage-count">
                            <strong>{Math.round(stg.share * 100)}%</strong>{' '}
                            <span className="muted">({stg.count})</span>
                          </span>
                        </div>
                        <div className="ins-funnel-bars">
                          <div className="ins-funnel-bar-line mono">
                            <span className="muted">standard</span>
                            <div className="ins-failure-bar-track">
                              <div
                                className="ins-failure-bar-fill"
                                style={{
                                  width: `${Math.max(stg.h1_count ? 2 : 0, h1Pct)}%`,
                                  background: 'var(--text-2)',
                                }}
                              />
                            </div>
                            <span className="num muted">{h1Pct}%</span>
                          </div>
                          <div className="ins-funnel-bar-line mono">
                            <span className="ins-h2-tag">extended</span>
                            <div className="ins-failure-bar-track">
                              <div
                                className="ins-failure-bar-fill"
                                style={{
                                  width: `${Math.max(stg.h2_count ? 2 : 0, h2Pct)}%`,
                                  background: 'var(--accent)',
                                }}
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
                <div className="ins-funnel-legend mono muted">
                  <span>By model</span>
                  {expModelFilter !== 'all' && (
                    <button
                      type="button"
                      className="ins-inline-reset mono"
                      onClick={() => setExpModelFilter('all')}
                    >
                      Clear ×
                    </button>
                  )}
                </div>
                <div className="table-wrap">
                  <table className="table ins-forensic-table">
                    <thead>
                      <tr>
                        <th>Model</th>
                        <th className="ins-col-mode">Mode</th>
                        <th className="num">Failed</th>
                        <th>Main Issue</th>
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
                            onClick={() => {
                              setExpModelFilter((cur) => (cur === key ? 'all' : key))
                              setVisibleCount(6)
                            }}
                          >
                            <td>
                              <strong>{friendlyPlayer(m.player_id)}</strong>
                              {m.harness_version === 'h2' && <span className="ins-h2-tag ins-mode-inline mono"> extended</span>}
                            </td>
                            <td className="mono ins-col-mode">
                              <span className={m.harness_version === 'h2' ? 'ins-h2-tag' : 'muted'}>
                                {m.harness_version === 'h2' ? 'extended' : 'standard'}
                              </span>
                            </td>
                            <td className="num mono">{m.total}</td>
                            <td>{friendlyStageShort(m.primary_bottleneck, m.primary_bottleneck)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </Panel>
      )}

      {/* 2. WHY MODELS FAILED — Concise, readable cards directly below the overview */}
      <div ref={whyFailedRef} id="why-models-failed">
        <Panel
          label={`Why Models Failed (${filteredExplanations.length})`}
          actions={
            hasFilters ? (
              <Button
                mono
                onClick={() => {
                  setExpStageFilter('all')
                  setExpRuleFilter('all')
                  setExpModelFilter('all')
                  setVisibleCount(6)
                }}
              >
                Reset filters
              </Button>
            ) : undefined
          }
        >
          <div className="ins-filter-bar">
            <div className="ins-metric-pills">
              {[
                { id: 'all', label: 'All' },
                { id: 'knowing_doing', label: 'Knew rule' },
                { id: 'h2', label: 'Extended only' },
                { id: 'perception', label: 'Misread' },
                { id: 'rule_induction', label: 'Missed rule' },
                { id: 'belief_updating', label: 'Looping' },
                { id: 'spatial_planning', label: 'Bad plan' },
                { id: 'budget_management', label: 'Late reset' },
              ].map((f) => (
                <Button
                  key={f.id}
                  mono
                  active={expStageFilter === f.id}
                  onClick={() => {
                    setExpStageFilter(f.id)
                    setVisibleCount(6)
                  }}
                >
                  {f.label}
                </Button>
              ))}
            </div>

            <select
              aria-label="Filter by rule"
              className="ins-rule-select mono"
              value={expRuleFilter}
              onChange={(e) => {
                setExpRuleFilter(e.target.value)
                setVisibleCount(6)
              }}
            >
              <option value="all">All rules ({explanationRules.length})</option>
              {explanationRules.map((r) => (
                <option key={r} value={r}>
                  {friendlyRule(r)}
                </option>
              ))}
            </select>
          </div>

          {!filteredExplanations.length ? (
            <Empty>No failures match this filter.</Empty>
          ) : (
            <>
              <div className="ins-exp-grid">
                {filteredExplanations.slice(0, visibleCount).map((ex) => {
                  const replayHref = `/replay/${encodeURIComponent(ex.run_id)}?step=${ex.step ?? 0}&xray=50`
                  const tkHref = buildTakeoverHref(ex.run_id, ex.step, ex.level, ex.game_id, ex.player_id)
                  const oneLiner = conciseSummary(ex.truth_contrast || ex.explanation)
                  const shortQuote = truncateQuote(ex.evidence_quote, 115)

                  return (
                    <div key={`${ex.run_id}-${ex.level}`} className="ins-exp-card">
                      <div className="ins-exp-card-head">
                        <strong>{friendlyPlayer(ex.player_id)}</strong>

                        <span className="ins-card-badges">
                          {ex.deduced_rule_in_cot && (
                            <span className="ins-kd-badge mono">
                              Knew rule{ex.deduced_rule_step != null ? ` at step ${ex.deduced_rule_step}` : ''}
                            </span>
                          )}
                          <Chip
                            outcome={
                              ex.cognitive_stage === 'spatial_planning' ||
                              ex.cognitive_stage === 'budget_management'
                                ? 'BUDGET'
                                : 'GAME_OVER'
                            }
                          >
                            {friendlyStageShort(ex.cognitive_stage, ex.verdict)}
                          </Chip>
                        </span>
                      </div>

                      {oneLiner && <p className="ins-exp-card-text">{oneLiner}</p>}

                      {shortQuote && (
                        <blockquote className="ins-exp-card-quote mono" title={ex.evidence_quote ?? undefined}>
                          “{shortQuote}”
                        </blockquote>
                      )}

                      <div className="ins-exp-card-foot mono">
                        <Link to={replayHref} className="ins-pill">
                          Watch from step {ex.step ?? 0}
                        </Link>
                        {tkHref && (
                          <Link to={tkHref} className="ins-takeover-pill" title="Take over the game at this step and play it yourself">
                            Try it yourself
                          </Link>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {filteredExplanations.length > visibleCount && (
                <div className="ins-load-more">
                  <Button mono onClick={() => setVisibleCount((c) => c + 8)}>
                    Show more ({filteredExplanations.length - visibleCount} left)
                  </Button>
                </div>
              )}
            </>
          )}
        </Panel>
      </div>

      {/* 3. SIMPLE SUPPORTING CHARTS */}
      <div className="ins-two-col">
        <Panel
          label="Score by Level"
          actions={
            learningCurve.length > 0 && (
              <Button
                mono
                active={curveMode === 'table'}
                onClick={() => setCurveMode((m) => (m === 'plot' ? 'table' : 'plot'))}
              >
                {curveMode === 'plot' ? 'Table' : 'Chart'}
              </Button>
            )
          }
        >
          {!learningCurve.length ? (
            <Empty>No level scores yet.</Empty>
          ) : curveMode === 'table' ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th className="num">Level</th>
                    <th>Player</th>
                    <th className="num">Solved</th>
                    <th className="num">Efficiency</th>
                  </tr>
                </thead>
                <tbody>
                  {learningCurve.map((pt) => (
                    <tr key={`${pt.level}-${pt.player_id}`}>
                      <td className="num mono">L{pt.level}</td>
                      <td>{friendlyPlayer(pt.player_id)}</td>
                      <td className="num mono">{(pt.solve_rate * 100).toFixed(0)}%</td>
                      <td className="num mono">{pt.mean_score.toFixed(3)}</td>
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
                height: 240,
                marginBottom: 36,
                x: {
                  label: 'Level (each level adds 1 new rule)',
                  tickFormat: (d: number) => `L${d}`,
                },
                y: { domain: [0, 1.04], label: 'Efficiency' },
                color: (() => {
                  // fixed per-player colours, same as the leaderboard (lib/modelColors.ts)
                  const byLabel = new Map(curvePlayers.map((p) => [p.playerLabel, playerColor({ id: p.player_id })]))
                  return { legend: true, domain: [...byLabel.keys()], range: [...byLabel.values()] }
                })(),
                marks: [
                  Plot.ruleY([1.0], { stroke: cssVar('--text-2') }),
                  Plot.lineY(curvePlayers, {
                    x: 'level',
                    y: 'mean_score',
                    stroke: 'playerLabel',
                    strokeWidth: 2,
                  }),
                  Plot.dot(curvePlayers, {
                    x: 'level',
                    y: 'mean_score',
                    fill: 'playerLabel',
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

        <Panel label="Common Mistakes">
          {!failureModes.length ? (
            <Empty>No mistake events recorded.</Empty>
          ) : (
            <div className="ins-failure-list">
              {failureModes.slice(0, 5).map((fm) => {
                const sharePct =
                  totalFailureEvents > 0 ? Math.round((fm.count / totalFailureEvents) * 100) : 0
                const barPct = Math.max(2, Math.round((fm.count / maxFailureCount) * 100))
                const isWarn = fm.mode === 'budget_exhaustion' || fm.mode === 'late_reset'
                return (
                  <div key={fm.mode} className="ins-failure-block">
                    <div className="ins-failure-head">
                      <span>{friendlyFailureMode(fm.mode)}</span>
                      <span className="mono muted">
                        {sharePct}% ({fm.count})
                      </span>
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
                      {fm.examples.slice(0, 2).map((ex, idx) => {
                        if (!ex.run_id) return null
                        const href = `/replay/${encodeURIComponent(ex.run_id)}${ex.step != null ? `?step=${ex.step}` : ''}`
                        return (
                          <Link key={`${fm.mode}-${idx}`} className="ins-evidence-chip" to={href}>
                            <span>{ex.player_id ? friendlyPlayer(ex.player_id) : 'Run'}</span>
                            <span className="ins-evidence-link">Step {ex.step ?? 0}</span>
                          </Link>
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

      {/* 4. COMPACT HARDEST RULES TABLE */}
      {ruleSummaryRows.length > 0 && (
        <Panel
          label="Hardest Rules for AI"
          actions={
            ruleSummaryRows.length > 8 ? (
              <Button mono onClick={() => setShowAllRules((v) => !v)}>
                {showAllRules ? 'Top 8' : `All ${ruleSummaryRows.length}`}
              </Button>
            ) : undefined
          }
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th className="num">AI Solve</th>
                  <th className="num">Human Solve</th>
                  <th className="num">Failures</th>
                </tr>
              </thead>
              <tbody>
                {(showAllRules ? ruleSummaryRows : ruleSummaryRows.slice(0, 8)).map((r) => {
                  const aiPct = r.aiSolveRate != null ? Math.round(r.aiSolveRate * 100) : null
                  return (
                    <tr key={r.rule}>
                      <td>
                        <span className="ins-rule-label">
                          <RuleSprite rule={r.rule} size={18} />
                          <strong>{r.label}</strong>
                        </span>
                      </td>
                      <td className="num mono">
                        {aiPct != null ? (
                          <div className="ins-inline-rate">
                            <span>{aiPct}%</span>
                            <div className="ins-inline-rate-track" aria-hidden="true">
                              <div
                                className="ins-inline-rate-fill"
                                style={{ width: `${Math.max(2, aiPct)}%` }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td className="num mono">
                        {r.humanSolveRate != null ? `${Math.round(r.humanSolveRate * 100)}%` : '—'}
                      </td>
                      <td className="num mono">
                        {r.failCases > 0 ? (
                          <Button
                            variant="ghost"
                            mono
                            onClick={() => jumpToFailures({ rule: r.rule, stage: 'all', model: 'all' })}
                          >
                            {r.failCases} ↑
                          </Button>
                        ) : (
                          <span className="muted">0</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  )
}
