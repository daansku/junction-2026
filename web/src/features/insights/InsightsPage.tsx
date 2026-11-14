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
import { PlotFigure, cssVar, seriesColors } from '@/lib/PlotFigure'
import type { RunMeta } from '@/lib/types'
import { fetchExplanations } from '@/features/play/epistemicApi'
import { RuleSprite } from '@/features/play/XrayOverlay'
import {
  STAGE_META,
  friendlyCause,
  friendlyFailureMode,
  friendlyPlayer,
  friendlyRule,
  friendlyStageShort,
  friendlyStageTitle,
} from './labels'
import type { RulesDocument, InsightsDocument } from './types'
import './insights.css'

const SEVERITY_OUTCOME: Record<string, string> = {
  high: 'GAME_OVER',
  medium: 'BUDGET',
  info: 'WIN',
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

  const whyFailedRef = useRef<HTMLDivElement | null>(null)
  const [curveMode, setCurveMode] = useState<'plot' | 'table'>('plot')
  const [expRuleFilter, setExpRuleFilter] = useState<string>('all')
  const [expStageFilter, setExpStageFilter] = useState<string>('all')
  const [expModelFilter, setExpModelFilter] = useState<string>('all')
  const [visibleCount, setVisibleCount] = useState<number>(12)
  const [showAllRules, setShowAllRules] = useState<boolean>(false)

  const insights = insightsQ.data?.insights ?? []
  const cells = rulesQ.data?.cells ?? []
  const learningCurve = rulesQ.data?.level_curve ?? rulesQ.data?.level_learning_curve ?? []
  const failureModes = rulesQ.data?.failure_modes ?? []
  const explanations = explanationsQ.data?.explanations ?? []
  const expSummary = explanationsQ.data?.summary ?? null

  const jumpToFailures = (opts: { stage?: string; rule?: string; model?: string }) => {
    if (opts.stage !== undefined) setExpStageFilter(opts.stage)
    if (opts.rule !== undefined) setExpRuleFilter(opts.rule)
    if (opts.model !== undefined) setExpModelFilter(opts.model)
    setVisibleCount(12)
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

  // Clean curve data with friendly player labels (top 4 distinct non-noop entities)
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

  // Compact "Hardest Rules for AI" summary (replaces the sprawling 20x18 matrix)
  const ruleSummaryRows = useMemo(() => {
    const byRule = new Map<
      string,
      {
        rule: string
        aiSolvedWeight: number
        aiLevels: number
        humanSolvedWeight: number
        humanLevels: number
        wastedSum: number
        wastedN: number
        failCases: number
      }
    >()

    const failCountByRule = new Map<string, number>()
    for (const ex of explanations) {
      if (ex.rule) failCountByRule.set(ex.rule, (failCountByRule.get(ex.rule) ?? 0) + 1)
    }

    for (const c of cells) {
      if (c.rule === 'goal' || c.rule === 'walls' || c.rule === 'move_budget') continue
      const isBase = c.player_id === 'optimal' || c.player_id === 'noop' || c.player_id === 'random' || c.player_id === 'stop_early'
      if (isBase) continue

      let entry = byRule.get(c.rule)
      if (!entry) {
        entry = {
          rule: c.rule,
          aiSolvedWeight: 0,
          aiLevels: 0,
          humanSolvedWeight: 0,
          humanLevels: 0,
          wastedSum: 0,
          wastedN: 0,
          failCases: failCountByRule.get(c.rule) ?? 0,
        }
        byRule.set(c.rule, entry)
      }

      const lvls = (c.intro_levels ?? 0) + (c.recombined_levels ?? 0)
      const rate =
        c.recombined_levels && c.recombined_solve_rate != null
          ? ((c.intro_levels * c.intro_solve_rate) + (c.recombined_levels * c.recombined_solve_rate)) / Math.max(1, lvls)
          : c.intro_solve_rate

      if (c.player_id === 'human') {
        if (lvls > 0) {
          entry.humanSolvedWeight += rate * lvls
          entry.humanLevels += lvls
        }
      } else {
        if (lvls > 0) {
          entry.aiSolvedWeight += rate * lvls
          entry.aiLevels += lvls
        }
        if (c.wasted_actions != null && !Number.isNaN(c.wasted_actions)) {
          entry.wastedSum += c.wasted_actions
          entry.wastedN += 1
        }
      }
    }

    return Array.from(byRule.values())
      .filter((r) => r.aiLevels > 0 || r.failCases > 0)
      .map((r) => ({
        rule: r.rule,
        label: friendlyRule(r.rule),
        aiSolveRate: r.aiLevels > 0 ? r.aiSolvedWeight / r.aiLevels : null,
        aiLevels: r.aiLevels,
        humanSolveRate: r.humanLevels > 0 ? r.humanSolvedWeight / r.humanLevels : null,
        avgWasted: r.wastedN > 0 ? r.wastedSum / r.wastedN : null,
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
      if (expModelFilter !== 'all' && `${e.player_id ?? ''}::${e.harness_version ?? 'h1'}` !== expModelFilter) return false
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

  const loading = insightsQ.isLoading || rulesQ.isLoading
  const error = insightsQ.error ?? rulesQ.error

  return (
    <div className="ins-stack">
      <PageHeader
        title="Why Models Fail"
        sub="We compare what each model wrote in its reasoning against the real game state to find the exact step it went wrong."
        actions={
          <div className="page-actions">
            <Link to="/leaderboard">
              <Button mono>← Leaderboard</Button>
            </Link>
            <Link to="/leaderboard?view=h2">
              <Button mono>Multi-Turn (h2)</Button>
            </Link>
            <Link to="/leaderboard?view=bench">
              <Button mono>Post-Training</Button>
            </Link>
            <Link to="/replay">
              <Button mono>All Replays</Button>
            </Link>
          </div>
        }
      />

      {loading ? (
        <Loading what="Loading failure diagnostics" />
      ) : error ? (
        <ErrorState
          error={error}
          retry={() => {
            insightsQ.refetch()
            rulesQ.refetch()
            explanationsQ.refetch()
          }}
        />
      ) : (
        <>
          {/* 1. IMMEDIATE HEADLINE INSIGHTS — 3 scannable cards above the fold */}
          {expSummary && (
            <section className="ins-hero-grid" aria-label="Key findings at a glance">
              <div className="ins-hero-card ins-hero-card-accent">
                <span className="kicker ins-hero-kicker">key finding 01 · knowing vs doing</span>
                <div className="ins-hero-stat mono">
                  <strong>{kdGapPct}%</strong>
                  <span>knew the rule, still failed</span>
                </div>
                <p className="ins-hero-desc">
                  In {expSummary.knowing_doing_gap_count} of {expSummary.non_tier0_failed_levels} hidden-rule failures, the model
                  correctly named the rule in its reasoning — then misplanned its path.
                </p>
                <div className="ins-hero-foot">
                  <Button
                    mono
                    active={expStageFilter === 'knowing_doing'}
                    onClick={() =>
                      jumpToFailures({ stage: expStageFilter === 'knowing_doing' ? 'all' : 'knowing_doing' })
                    }
                  >
                    {expStageFilter === 'knowing_doing'
                      ? 'Showing these cases'
                      : `Show ${expSummary.knowing_doing_gap_count} cases ↓`}
                  </Button>
                </div>
              </div>

              <div className="ins-hero-card">
                <span className="kicker ins-hero-kicker">key finding 02 · memory vs planning</span>
                <div className="ins-hero-stat mono">
                  <strong>
                    {h1PerceptionPct}% → {h2PerceptionPct}%
                  </strong>
                  <span>board-reading mistakes</span>
                </div>
                <p className="ins-hero-desc">
                  Giving models full chat history (<span className="mono">h2</span>) eliminates coordinate misreads, shifting
                  remaining failures to rule discovery and multi-step planning.
                </p>
                <div className="ins-hero-foot">
                  <Button
                    mono
                    active={expStageFilter === 'h2'}
                    onClick={() => jumpToFailures({ stage: expStageFilter === 'h2' ? 'all' : 'h2' })}
                  >
                    {expStageFilter === 'h2' ? 'Showing h2 cases' : 'Show multi-turn (h2) cases ↓'}
                  </Button>
                </div>
              </div>

              <div className="ins-hero-card">
                <span className="kicker ins-hero-kicker">key finding 03 · verified step-by-step</span>
                <div className="ins-hero-stat mono">
                  <strong>{explanations.length}</strong>
                  <span>failed levels audited</span>
                </div>
                <p className="ins-hero-desc">
                  Every diagnosis below quotes the model’s exact words alongside real engine truth and opens that step live with X-Ray.
                </p>
                <div className="ins-hero-foot">
                  <Button
                    mono
                    onClick={() => jumpToFailures({ stage: 'all', rule: 'all', model: 'all' })}
                  >
                    Browse all {explanations.length} cases ↓
                  </Button>
                </div>
              </div>
            </section>
          )}

          {/* 2. CLEAR FAILURE OVERVIEW — Where attempts break down (h1 vs h2) + By Model */}
          {expSummary && expSummary.by_cognitive_stage?.length > 0 && (
            <Panel
              label="Failure Overview · Where Models Break Down"
              actions={
                <span className="mono muted">
                  click any reason or model to filter the traces below
                </span>
              }
            >
              <div className="ins-forensic-split">
                <div className="ins-funnel-col">
                  <div className="ins-funnel-legend mono muted">
                    <span>Failure stage (from basic vision to multi-step planning)</span>
                    <span>
                      <i className="ins-swatch-h1" /> Single-turn h1 ({expSummary.by_harness.h1?.total ?? 0}) ·{' '}
                      <i className="ins-swatch-h2" /> Multi-turn h2 ({expSummary.by_harness.h2?.total ?? 0})
                    </span>
                  </div>
                  <div className="ins-funnel-list">
                    {expSummary.by_cognitive_stage.map((stg) => {
                      const active = expStageFilter === stg.stage
                      const h1Pct = Math.round(stg.h1_share * 100)
                      const h2Pct = Math.round(stg.h2_share * 100)
                      const meta = STAGE_META[stg.stage]
                      return (
                        <button
                          type="button"
                          key={stg.stage}
                          className={cx('ins-funnel-row', active && 'ins-funnel-row-active')}
                          onClick={() =>
                            setExpStageFilter((cur) => (cur === stg.stage ? 'all' : stg.stage))
                          }
                        >
                          <div className="ins-funnel-row-top">
                            <div>
                              <strong className="ins-stage-title">
                                {friendlyStageTitle(stg.stage, stg.label)}
                              </strong>
                              {meta?.hint && <span className="ins-stage-hint">{meta.hint}</span>}
                            </div>
                            <span className="mono ins-stage-count">
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
                                  style={{
                                    width: `${Math.max(stg.h1_count ? 2 : 0, h1Pct)}%`,
                                    background: 'var(--text-2)',
                                  }}
                                />
                              </div>
                              <span className="num muted">{h1Pct}%</span>
                            </div>
                            <div className="ins-funnel-bar-line mono">
                              <span className="ins-h2-tag">h2</span>
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
                    <span>Breakdown by model (click a row to filter)</span>
                    {expModelFilter !== 'all' && (
                      <button
                        type="button"
                        className="ins-inline-reset mono"
                        onClick={() => setExpModelFilter('all')}
                      >
                        Clear model filter ×
                      </button>
                    )}
                  </div>
                  <div className="table-wrap ins-forensic-table-wrap">
                    <table className="table ins-forensic-table">
                      <thead>
                        <tr>
                          <th>Model</th>
                          <th>Mode</th>
                          <th className="num">Failed</th>
                          <th className="num">Knew Rule</th>
                          <th>#1 Failure Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {expSummary.by_model.slice(0, 10).map((m) => {
                          const key = `${m.player_id}::${m.harness_version}`
                          const active = expModelFilter === key
                          return (
                            <tr
                              key={key}
                              className={cx('ins-clickable-row', active && 'ins-row-selected')}
                              onClick={() => {
                                setExpModelFilter((cur) => (cur === key ? 'all' : key))
                                setVisibleCount(12)
                              }}
                            >
                              <td>
                                <strong>{friendlyPlayer(m.player_id)}</strong>
                              </td>
                              <td className="mono">
                                <span className={m.harness_version === 'h2' ? 'ins-h2-tag' : 'muted'}>
                                  {m.harness_version === 'h2' ? 'h2 multi-turn' : 'h1 single-turn'}
                                </span>
                              </td>
                              <td className="num mono">{m.total}</td>
                              <td className="num mono">{(m.knowing_doing_gap_rate * 100).toFixed(0)}%</td>
                              <td>{friendlyStageShort(m.primary_bottleneck, m.primary_bottleneck)}</td>
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

          {/* 3. IMMEDIATELY BELOW OVERVIEW: WHY MODELS FAILED (Step-by-step traces) */}
          <div ref={whyFailedRef} id="why-models-failed">
            <Panel
              label={`Why Models Failed · ${filteredExplanations.length} Audited Level Failures`}
              actions={
                <div className="ins-ledger-head-actions mono">
                  {(expStageFilter !== 'all' || expRuleFilter !== 'all' || expModelFilter !== 'all') && (
                    <Button
                      mono
                      onClick={() => {
                        setExpStageFilter('all')
                        setExpRuleFilter('all')
                        setExpModelFilter('all')
                        setVisibleCount(12)
                      }}
                    >
                      Reset Filters
                    </Button>
                  )}
                  <span className="muted">real engine state vs model reasoning</span>
                </div>
              }
            >
              <div className="ins-filter-bar">
                <div className="ins-metric-pills">
                  {[
                    { id: 'all', label: `All (${explanations.length})` },
                    { id: 'knowing_doing', label: 'Knew Rule, Still Failed' },
                    { id: 'h2', label: 'Multi-Turn (h2)' },
                    { id: 'perception', label: '1 · Misread Board' },
                    { id: 'rule_induction', label: '2 · Missed Rule' },
                    { id: 'belief_updating', label: '3 · Stuck Looping' },
                    { id: 'spatial_planning', label: '4 · Bad Plan' },
                    { id: 'budget_management', label: '5 · Late Reset' },
                  ].map((f) => (
                    <Button
                      key={f.id}
                      mono
                      active={expStageFilter === f.id}
                      onClick={() => {
                        setExpStageFilter(f.id)
                        setVisibleCount(12)
                      }}
                    >
                      {f.label}
                    </Button>
                  ))}
                </div>

                <label className="ins-rule-select-wrap mono">
                  <span className="muted">Rule:</span>
                  <select
                    className="ins-rule-select mono"
                    value={expRuleFilter}
                    onChange={(e) => {
                      setExpRuleFilter(e.target.value)
                      setVisibleCount(12)
                    }}
                  >
                    <option value="all">All game rules ({explanationRules.length})</option>
                    {explanationRules.map((r) => (
                      <option key={r} value={r}>
                        {friendlyRule(r)} ({r})
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {!filteredExplanations.length ? (
                <Empty>No level failures match the active filter.</Empty>
              ) : (
                <>
                  <div className="ins-exp-grid">
                    {filteredExplanations.slice(0, visibleCount).map((ex) => {
                      const replayHref = `/replay/${encodeURIComponent(ex.run_id)}?step=${ex.step ?? 0}&xray=50`
                      const tkHref = buildTakeoverHref(ex.run_id, ex.step, ex.level, ex.game_id, ex.player_id)
                      const quoteFrom =
                        ex.quote_source === 'reasoning'
                          ? ex.harness_version === 'h2'
                            ? 'thinking trace'
                            : 'scratchpad notes'
                          : 'hypothesis'
                      return (
                        <div key={`${ex.run_id}-${ex.level}`} className="ins-exp-card">
                          <div className="ins-exp-card-head">
                            <span className="ins-rule-label">
                              {ex.rule && <RuleSprite rule={ex.rule} size={18} />}
                              <strong>{friendlyPlayer(ex.player_id)}</strong>
                              {ex.harness_version && (
                                <span
                                  className={cx(
                                    'ins-hrn-badge mono',
                                    ex.harness_version === 'h2' && 'ins-hrn-h2',
                                  )}
                                >
                                  {ex.harness_version === 'h2' ? 'h2 multi-turn' : 'h1'}
                                </span>
                              )}
                              <span className="mono muted">· Level {ex.level}</span>
                              {ex.rule && (
                                <span className="ins-rule-tag mono">{friendlyRule(ex.rule)}</span>
                              )}
                            </span>
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
                          </div>

                          <div className="ins-exp-submeta mono">
                            <span className="muted">{friendlyCause(ex.root_cause ?? ex.verdict)}</span>
                            {ex.deduced_rule_in_cot && (
                              <span className="ins-kd-badge">
                                KNEW RULE{ex.deduced_rule_step != null ? ` @STEP ${ex.deduced_rule_step}` : ''}
                              </span>
                            )}
                          </div>

                          {ex.truth_contrast && (
                            <div className="ins-truth-contrast">
                              <span className="mono ins-truth-kicker">REALITY vs MODEL</span>{' '}
                              {ex.truth_contrast}
                            </div>
                          )}

                          {ex.explanation && <p className="ins-exp-card-text">{ex.explanation}</p>}

                          {ex.evidence_quote && (
                            <blockquote className="ins-exp-card-quote mono">
                              <span className="ins-quote-kicker">Model wrote ({quoteFrom}):</span> “{ex.evidence_quote}”
                            </blockquote>
                          )}

                          <div className="ins-exp-card-foot mono">
                            <Link
                              to={replayHref}
                              className="ins-pill"
                              title="Open this exact failure step with the 50% X-Ray truth curtain"
                            >
                              Watch Step @{ex.step ?? 0} with X-Ray →
                            </Link>
                            {tkHref && (
                              <Link to={tkHref} className="ins-takeover-pill">
                                [ Play From Step @{ex.step ?? 1} ]
                              </Link>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {filteredExplanations.length > visibleCount && (
                    <div className="ins-load-more">
                      <Button
                        mono
                        onClick={() => setVisibleCount((c) => c + 12)}
                      >
                        Show 12 More ({filteredExplanations.length - visibleCount} remaining)
                      </Button>
                    </div>
                  )}
                </>
              )}
            </Panel>
          </div>

          {/* 4. SUPPORTING STATISTICS WITH SIMPLE NAMES */}
          <div className="ins-two-col">
            <Panel
              label="How Scores Drop as Levels Add More Rules"
              actions={
                learningCurve.length > 0 && (
                  <Button
                    mono
                    active={curveMode === 'table'}
                    onClick={() => setCurveMode((m) => (m === 'plot' ? 'table' : 'plot'))}
                  >
                    {curveMode === 'plot' ? 'Show Table' : 'Show Chart'}
                  </Button>
                )
              }
            >
              {!learningCurve.length ? (
                <Empty>No per-level scores recorded yet.</Empty>
              ) : curveMode === 'table' ? (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th className="num">Level</th>
                        <th>Player</th>
                        <th className="num">Attempts</th>
                        <th className="num">Solve Rate</th>
                        <th className="num">Avg Score</th>
                        <th className="num">Avg Moves</th>
                      </tr>
                    </thead>
                    <tbody>
                      {learningCurve.map((pt) => (
                        <tr key={`${pt.level}-${pt.player_id}`}>
                          <td className="num mono">Level {pt.level}</td>
                          <td>{friendlyPlayer(pt.player_id)}</td>
                          <td className="num mono">{pt.attempts}</td>
                          <td className="num mono">{(pt.solve_rate * 100).toFixed(0)}%</td>
                          <td className="num mono">{pt.mean_score.toFixed(3)}</td>
                          <td className="num mono">
                            {pt.mean_actions != null ? pt.mean_actions.toFixed(1) : '—'}
                          </td>
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
                    height: 255,
                    marginBottom: 38,
                    x: {
                      label: 'Level in game (each new level adds another hidden rule)',
                      tickFormat: (d: number) => `L${d}`,
                    },
                    y: { domain: [0, 1.04], label: 'Average score (1.0 = optimal moves)' },
                    color: { legend: true, range: seriesColors() },
                    marks: [
                      Plot.ruleY([1.0], {
                        stroke: cssVar('--text-2'),
                      }),
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

            <Panel label="Most Common In-Game Mistakes (Jump In & Play)">
              {!failureModes.length ? (
                <Empty>Zero mistake events detected across loaded runs.</Empty>
              ) : (
                <div className="ins-failure-list">
                  {failureModes.map((fm) => {
                    const sharePct =
                      totalFailureEvents > 0 ? Math.round((fm.count / totalFailureEvents) * 100) : 0
                    const barPct = Math.max(2, Math.round((fm.count / maxFailureCount) * 100))
                    const isWarn = fm.mode === 'budget_exhaustion' || fm.mode === 'late_reset'
                    return (
                      <div key={fm.mode} className="ins-failure-block">
                        <div className="ins-failure-head">
                          <span>
                            <strong>{friendlyFailureMode(fm.mode)}</strong>{' '}
                            <span className="mono muted">({sharePct}%)</span>
                          </span>
                          <Chip outcome={isWarn ? 'BUDGET' : 'GAME_OVER'}>
                            {fm.count}×
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
                          {fm.examples.slice(0, 3).map((ex, idx) => {
                            if (!ex.run_id) return null
                            const href = `/replay/${encodeURIComponent(ex.run_id)}${ex.step != null ? `?step=${ex.step}` : ''}`
                            const tkHref = buildTakeoverHref(
                              ex.run_id,
                              ex.step,
                              ex.level,
                              null,
                              ex.player_id,
                            )
                            return (
                              <span key={`${fm.mode}-${idx}`} className="ins-evidence-group">
                                <Link className="ins-evidence-chip" to={href} title={ex.run_id}>
                                  <span>{ex.player_id ? friendlyPlayer(ex.player_id) : 'Run'}</span>
                                  {ex.level != null && <span className="muted">L{ex.level}</span>}
                                  <span className="ins-evidence-link">
                                    @{ex.step ?? 0} →
                                  </span>
                                </Link>
                                {tkHref && (
                                  <Link className="ins-takeover-pill mono" to={tkHref}>
                                    [ Play{ex.step != null ? ` @${ex.step}` : ''} ]
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

          {/* 5. KEY BENCHMARK TAKEAWAYS (concise replay-backed cards) */}
          {insights.length > 0 && (
            <Panel label="Additional Benchmark Takeaways (Pinned to Replays)">
              <div className="ins-findings-grid">
                {insights.map((ins) => (
                  <Panel
                    key={ins.id}
                    label={ins.category ? ins.category.replace(/_/g, ' ') : 'takeaway'}
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
                                : ev.value.toFixed(3).replace(/\.?0+$/, '')
                              : String(ev.value)
                          const replayHref = ev.run_id
                            ? `/replay/${encodeURIComponent(ev.run_id)}${ev.step != null ? `?step=${ev.step}` : ''}`
                            : null
                          return replayHref && ev.run_id ? (
                            <Link
                              key={`${ev.label}-${i}`}
                              className="ins-evidence-chip"
                              to={replayHref}
                              title={ev.run_id}
                            >
                              <span className="muted">{ev.label}:</span>
                              <strong>{displayVal}</strong>
                              <span className="ins-evidence-link">
                                #{shortRunId(ev.run_id)}
                                {ev.step != null ? ` · @${ev.step}` : ''} →
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
            </Panel>
          )}

          {/* 6. COMPACT RULE DIFFICULTY TABLE (replaces the cluttered 20x18 Rule x Player Matrix) */}
          {ruleSummaryRows.length > 0 && (
            <Panel
              label="Hardest Game Rules for AI (Human vs Model Solve Rate)"
              actions={
                ruleSummaryRows.length > 10 ? (
                  <Button
                    mono
                    onClick={() => setShowAllRules((v) => !v)}
                  >
                    {showAllRules ? 'Show Top 10 Hardest' : `Show All ${ruleSummaryRows.length} Rules`}
                  </Button>
                ) : undefined
              }
            >
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Game Rule</th>
                      <th className="num">AI Solve Rate</th>
                      <th className="num">Human Solve Rate</th>
                      <th className="num">Avg Extra Moves (AI)</th>
                      <th className="num">Audited Failures</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(showAllRules ? ruleSummaryRows : ruleSummaryRows.slice(0, 10)).map((r) => {
                      const aiPct = r.aiSolveRate != null ? Math.round(r.aiSolveRate * 100) : null
                      return (
                        <tr key={r.rule}>
                          <td>
                            <span className="ins-rule-label">
                              <RuleSprite rule={r.rule} size={18} />
                              <strong>{r.label}</strong>
                              <span className="mono muted">({r.rule})</span>
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
                            {r.avgWasted != null ? `+${r.avgWasted.toFixed(1)}` : '—'}
                          </td>
                          <td className="num mono">
                            {r.failCases > 0 ? (
                              <Button
                                variant="ghost"
                                mono
                                onClick={() => jumpToFailures({ rule: r.rule, stage: 'all', model: 'all' })}
                              >
                                {r.failCases} cases ↑
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
        </>
      )}
    </div>
  )
}
