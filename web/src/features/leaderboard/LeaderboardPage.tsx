import * as Plot from '@observablehq/plot'
import { useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Button,
  Chip,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Panel,
  Stat,
  Swatch,
  cx,
} from '@/design/primitives'
import { api } from '@/lib/api'
import { PlotFigure, cssVar, seriesColors } from '@/lib/PlotFigure'
import type { RunMeta } from '@/lib/types'
import { fetchBenchSummary, fetchDecisionPoints, fetchLeaderboardH2 } from './phase2Api'
import { LeaderboardH2View, PostTrainingBenchView } from './PostTrainingSection'
import type { LeaderboardDocument, LeaderboardRow } from './types'
import './leaderboard.css'

type BoardView = 'h1' | 'h2' | 'bench'

type SortKey =
  | 'score'
  | 'level_solve_rate'
  | 'game_win_rate'
  | 'median_actions'
  | 'cost_per_game'
  | 'cost_per_solved_level'
  | 'latency_ms_median'
  | 'resets_total'
  | 'no_effect_rate'
  | 'belief_accuracy'

type KindFilter = 'all' | 'model' | 'baseline' | 'human'

const EFFORT_RANK: Record<string, number> = {
  low: 0,
  medium: 1,
  high: 2,
  xhigh: 3,
  max: 4,
}

const HIGHER_IS_BETTER = new Set<SortKey>([
  'score',
  'level_solve_rate',
  'game_win_rate',
  'belief_accuracy',
])

function fmtFloat(v: number | null | undefined, digits = 3): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `$${v.toFixed(v < 0.01 ? 4 : 3)}`
}

function fmtInt(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return Math.round(v).toLocaleString()
}

function fmtTokensCompact(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v >= 10_000_000 ? 0 : 1)}M`
  if (v >= 1_000) return `${Math.round(v / 1_000)}k`
  return String(Math.round(v))
}

function rowModes(row: LeaderboardRow): string {
  const modes = row.input_modes ?? row.model?.input_modes
  return modes && modes.length ? modes.join('+') : '—'
}

function rowLabel(row: LeaderboardRow): string {
  const base = row.display_name || row.model?.display_name || row.player_id
  return row.effort ? `${base} (${row.effort})` : base
}

function rowProvider(row: LeaderboardRow): string | null {
  return row.model?.provider || row.provider || null
}

export function seriesColorFor(row: LeaderboardRow, fallbackIndex: number): string {
  if (row.kind === 'baseline') return cssVar('--text-3') || '#76756f'
  const colors = seriesColors()
  const paletteIndex =
    row.model_order != null && row.model_order < 900
      ? Math.abs(row.model_order) % colors.length
      : fallbackIndex % colors.length
  return colors[paletteIndex] || cssVar('--accent')
}

function runRankScore(r: RunMeta): number {
  return (r.outcome === 'WIN' ? 1e7 : 0) + (r.levels_completed ?? 0) * 1e4 - (r.actions ?? 0)
}

export function LeaderboardPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawView = searchParams.get('view')
  const view: BoardView = rawView === 'h2' || rawView === 'bench' ? rawView : 'h1'

  const setView = (next: BoardView) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next === 'h1') nextParams.delete('view')
    else nextParams.set('view', next)
    setSearchParams(nextParams, { replace: true })
  }

  const lb = useQuery({
    queryKey: ['derived', 'leaderboard'],
    queryFn: () => api.derived<LeaderboardDocument>('leaderboard'),
  })
  const lbH2 = useQuery({
    queryKey: ['derived', 'leaderboard_h2'],
    queryFn: fetchLeaderboardH2,
  })
  const benchQ = useQuery({
    queryKey: ['derived', 'bench_summary'],
    queryFn: fetchBenchSummary,
  })
  const decisionPtsQ = useQuery({
    queryKey: ['derived', 'decision_points'],
    queryFn: fetchDecisionPoints,
  })
  const runsQ = useQuery({
    queryKey: ['runs', 'lb-best-lookup'],
    queryFn: () => api.listRuns(),
    staleTime: 60_000,
  })

  const [collection, setCollection] = useState<string>('all')
  const [kindFilter, setKindFilter] = useState<KindFilter>('all')
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [frontierMode, setFrontierMode] = useState<'chart' | 'table'>('chart')
  const [frontierAxis, setFrontierAxis] = useState<'auto' | 'tokens' | 'usd'>('auto')
  const [effortMode, setEffortMode] = useState<'chart' | 'table'>('chart')

  const allRows = lb.data?.rows ?? []

  // Map each player_id (and effort) to its best finished recorded run for 1-click scatter/ledger replay navigation
  const bestRunByPlayer = useMemo(() => {
    const map = new Map<string, string>()
    const bestScore = new Map<string, number>()
    for (const r of runsQ.data ?? []) {
      if (!r.outcome || r.outcome === 'IN_PROGRESS') continue
      const pid =
        r.player?.kind === 'human'
          ? 'human'
          : r.player?.kind === 'baseline'
            ? (r.player.model_id ?? r.player.name ?? '').replace(/^baseline:/, '')
            : (r.player?.model_id ?? r.player?.name ?? '')
      if (!pid) continue
      const s = runRankScore(r)
      const keys = [pid, `${pid}::${r.player?.effort ?? ''}`]
      for (const k of keys) {
        if (s > (bestScore.get(k) ?? -Infinity)) {
          bestScore.set(k, s)
          map.set(k, r.run_id)
        }
      }
    }
    return map
  }, [runsQ.data])

  const resolveBestRun = (row: LeaderboardRow): string | null =>
    row.best_run_id ?? bestRunByPlayer.get(`${row.player_id}::${row.effort ?? ''}`) ?? bestRunByPlayer.get(row.player_id) ?? null

  const collections = useMemo(() => {
    const set = new Set<string>()
    for (const r of allRows) set.add(r.collection || 'dev')
    return ['all', ...Array.from(set).sort()]
  }, [allRows])

  const collectionRows = useMemo(() => {
    if (collection === 'all') return allRows
    return allRows.filter((r) => r.collection === collection)
  }, [allRows, collection])

  const filteredRows = useMemo(() => {
    if (kindFilter === 'all') return collectionRows
    return collectionRows.filter((r) => r.kind === kindFilter)
  }, [collectionRows, kindFilter])

  const sortedRows = useMemo(() => {
    const copy = [...filteredRows]
    copy.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      const cmp = Number(av) - Number(bv)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [filteredRows, sortKey, sortDir])

  const bestValues = useMemo(() => {
    const keys: SortKey[] = [
      'score',
      'level_solve_rate',
      'game_win_rate',
      'median_actions',
      'cost_per_game',
      'cost_per_solved_level',
      'latency_ms_median',
      'resets_total',
      'no_effect_rate',
      'belief_accuracy',
    ]
    const out: Partial<Record<SortKey, number>> = {}
    for (const k of keys) {
      const vals = sortedRows
        .map((r) => r[k])
        .filter((v): v is number => typeof v === 'number' && !Number.isNaN(v))
      if (!vals.length) continue
      out[k] = HIGHER_IS_BETTER.has(k) ? Math.max(...vals) : Math.min(...vals)
    }
    return out
  }, [sortedRows])

  const kpi = useMemo(() => {
    const modelRows = collectionRows.filter((r) => r.kind === 'model')
    const bestModel = modelRows.reduce<LeaderboardRow | null>(
      (best, cur) => (!best || cur.score > best.score ? cur : best),
      null,
    )
    const optRow = collectionRows.find((r) => r.player_id === 'optimal')
    const humanRow = collectionRows.find((r) => r.kind === 'human' || r.player_id === 'human')
    const randomRow = collectionRows.find((r) => r.player_id === 'random')
    const noopRow = collectionRows.find((r) => r.player_id === 'noop')
    const stopRow = collectionRows.find((r) => r.player_id === 'stop_early')
    const totalGames = collectionRows.reduce((acc, r) => acc + (r.games || 0), 0)
    const integrityOk =
      (noopRow == null || noopRow.score === 0) &&
      (stopRow == null || stopRow.score === 0) &&
      (optRow == null || optRow.score >= 0.999)

    return {
      totalGames,
      modelCount: modelRows.length,
      bestModel,
      optScore: optRow?.score ?? 1.0,
      humanScore: humanRow?.score ?? null,
      randomScore: randomRow?.score ?? null,
      noopScore: noopRow?.score ?? null,
      stopScore: stopRow?.score ?? null,
      integrityOk,
    }
  }, [collectionRows])

  const hasUnpricedTokenModels = useMemo(
    () =>
      collectionRows.some(
        (r) =>
          r.kind === 'model' &&
          (r.cost_per_game == null || r.cost_per_game <= 0) &&
          (r.tokens_in ?? 0) + (r.tokens_out ?? 0) > 0,
      ),
    [collectionRows],
  )

  const effectiveAxis: 'tokens' | 'usd' =
    frontierAxis === 'auto' ? (hasUnpricedTokenModels ? 'tokens' : 'usd') : frontierAxis

  const frontierPoints = useMemo(
    () =>
      collectionRows
        .map((row, idx) => {
          const totalTokens = (row.tokens_in ?? 0) + (row.tokens_out ?? 0)
          const tokensPerGame = row.games > 0 ? totalTokens / row.games : 0
          const xVal = effectiveAxis === 'usd' ? (row.cost_per_game ?? 0) : tokensPerGame
          return {
            row,
            label: rowLabel(row),
            xVal,
            cost: row.cost_per_game ?? null,
            tokensPerGame,
            score: row.score,
            color: seriesColorFor(row, idx),
            runId: bestRunByPlayer.get(`${row.player_id}::${row.effort ?? ''}`) ?? bestRunByPlayer.get(row.player_id) ?? null,
          }
        })
        .filter((pt) => pt.row.kind === 'model' && pt.xVal > 0),
    [collectionRows, effectiveAxis, bestRunByPlayer],
  )

  const hasHoldout = useMemo(
    () =>
      sortedRows.some(
        (r) =>
          r.seen_score != null || r.unseen_pair_score != null || r.unseen_skin_score != null,
      ),
    [sortedRows],
  )

  const effortSeries = useMemo(() => {
    const grouped = new Map<string, LeaderboardRow[]>()
    for (const r of collectionRows) {
      if (r.kind !== 'model' || !r.effort) continue
      const key = `${r.player_id}::${r.collection}`
      const list = grouped.get(key) ?? []
      list.push(r)
      grouped.set(key, list)
    }
    const multi: Array<{
      player_id: string
      label: string
      effort: string
      effortRank: number
      score: number
      cost: number | null
    }> = []
    for (const items of grouped.values()) {
      if (items.length < 2) continue
      const sorted = [...items].sort(
        (a, b) => (EFFORT_RANK[a.effort || ''] ?? 99) - (EFFORT_RANK[b.effort || ''] ?? 99),
      )
      for (const it of sorted) {
        multi.push({
          player_id: it.player_id,
          label: it.display_name || it.player_id,
          effort: it.effort || 'default',
          effortRank: EFFORT_RANK[it.effort || ''] ?? 99,
          score: it.score,
          cost: it.cost_per_game ?? null,
        })
      }
    }
    return multi
  }, [collectionRows])

  const registeredCards = useMemo(() => {
    const seen = new Set<string>()
    const list: Array<{ row: LeaderboardRow; color: string }> = []
    collectionRows.forEach((r, idx) => {
      if (r.kind !== 'model') return
      if (seen.has(r.player_id)) return
      seen.add(r.player_id)
      list.push({ row: r, color: seriesColorFor(r, idx) })
    })
    return list
  }, [collectionRows])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortKey(key)
      setSortDir(HIGHER_IS_BETTER.has(key) ? 'desc' : 'asc')
    }
  }

  const sortArrow = (key: SortKey) =>
    sortKey === key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''

  // Click-to-replay on Observable Plot SVG scatter dots
  const onScatterClick = (e: ReactMouseEvent<HTMLDivElement>) => {
    const target = e.target as Element | null
    if (!target) return
    const circle = target.closest('circle')
    if (!circle) return
    const group = circle.parentElement
    if (!group) return
    const circles = Array.from(group.querySelectorAll('circle'))
    const idx = circles.indexOf(circle)
    const pt = frontierPoints[idx]
    if (pt?.runId) {
      navigate(`/replay/${encodeURIComponent(pt.runId)}`)
    }
  }

  const holdoutCols = hasHoldout ? 3 : 0

  return (
    <div className="lb-stack">
      <PageHeader
        title="Benchmark Leaderboard"
        sub="Action-efficiency scoring across stateless rolling-notes (h1), lab-standard multi-turn (h2), and post-training transfer."
        actions={
          <div className="page-actions">
            {lb.data?.generated_at && (
              <span className="mono muted">
                built {lb.data.generated_at.replace('T', ' ').replace('Z', ' UTC')}
              </span>
            )}
            <Link to="/challenge">
              <Button mono>Beat the AI →</Button>
            </Link>
            <Link to="/insights">
              <Button mono>Insights &amp; Rules →</Button>
            </Link>
          </div>
        }
      />

      <div className="lb-view-tabs" role="tablist" aria-label="Evaluation harness and post-training views">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'h1'}
          className={cx('lb-view-tab mono', view === 'h1' && 'active')}
          onClick={() => setView('h1')}
        >
          <span>h1 · Stateless Rolling-Notes</span>
          <span className="lb-tab-count">{allRows.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'h2'}
          className={cx('lb-view-tab mono', view === 'h2' && 'active')}
          onClick={() => setView('h2')}
        >
          <span>h2 · Lab-Standard Multi-Turn</span>
          <span className="lb-tab-count">{lbH2.data?.rows.length ?? '—'}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'bench'}
          className={cx('lb-view-tab mono', view === 'bench' && 'active')}
          onClick={() => setView('bench')}
        >
          <span>Post-Training &amp; Reasoning Transfer</span>
          <span className="lb-tab-count">Qwen3.5-9B</span>
        </button>
      </div>

      {view === 'h2' ? (
        <LeaderboardH2View
          doc={lbH2.data}
          isLoading={lbH2.isLoading}
          resolveRunFallback={resolveBestRun}
        />
      ) : view === 'bench' ? (
        <PostTrainingBenchView
          bench={benchQ.data}
          decisionPoints={decisionPtsQ.data}
          isLoading={benchQ.isLoading}
        />
      ) : lb.isLoading ? (
        <Loading what="Loading leaderboard" />
      ) : lb.error ? (
        <ErrorState error={lb.error} retry={() => lb.refetch()} />
      ) : !allRows.length ? (
        <Empty action={<Link to="/play">Play a game</Link>}>
          No evaluated runs found yet.
        </Empty>
      ) : (
        <>
          <div className="lb-kpi-grid" aria-label="Headline benchmark summary">
            <div className="lb-kpi-cell">
              <Stat
                label="Best Evaluated Model"
                value={kpi.bestModel ? fmtFloat(kpi.bestModel.score, 3) : '—'}
                unit="eff."
                sub={
                  kpi.bestModel
                    ? `${rowLabel(kpi.bestModel)} · gap ${(kpi.optScore - kpi.bestModel.score).toFixed(3)} to optimal`
                    : 'No LLM runs scored yet'
                }
              />
            </div>
            <div className="lb-kpi-cell">
              <Stat
                label="Reference Ceiling"
                value={fmtFloat(kpi.optScore, 3)}
                unit="optimal"
                sub={
                  kpi.humanScore != null
                    ? `Human ${fmtFloat(kpi.humanScore, 3)} · Random ${fmtFloat(kpi.randomScore, 3)}`
                    : `Random baseline ${fmtFloat(kpi.randomScore, 3)}`
                }
              />
            </div>
            <div className="lb-kpi-cell">
              <Stat
                label="Evaluated Volume"
                value={kpi.totalGames}
                unit="game runs"
                sub={`${collectionRows.length} entries · ${kpi.modelCount} model configs`}
              />
            </div>
            <div className="lb-kpi-cell">
              <div className="stat">
                <span className="kicker">Reward Integrity</span>
                <div style={{ marginTop: 4 }}>
                  <Chip outcome={kpi.integrityOk ? 'WIN' : 'GAME_OVER'}>
                    {kpi.integrityOk ? 'VERIFIED ZERO-EXPLOIT' : 'CHECK FAILED'}
                  </Chip>
                </div>
                <span className="stat-sub mono">
                  noop {fmtFloat(kpi.noopScore, 3)} · stop_early {fmtFloat(kpi.stopScore, 3)}
                </span>
              </div>
            </div>
          </div>

          <div className="lb-controls">
            <div className="lb-filter-group">
              <span className="kicker lb-filter-label">Collection</span>
              {collections.map((c) => (
                <Button
                  key={c}
                  mono
                  active={collection === c}
                  onClick={() => setCollection(c)}
                >
                  {c}
                </Button>
              ))}
            </div>
            <div className="lb-filter-group">
              <span className="kicker lb-filter-label">Player kind</span>
              {(['all', 'model', 'baseline', 'human'] as KindFilter[]).map((k) => (
                <Button
                  key={k}
                  mono
                  active={kindFilter === k}
                  onClick={() => setKindFilter(k)}
                >
                  {k}
                </Button>
              ))}
            </div>
          </div>

          <Panel
            label={
              effectiveAxis === 'tokens'
                ? 'Compute (Tokens / Game) vs Action-Efficiency Frontier · Click Dot for Replay'
                : 'Cost (USD / Game) vs Action-Efficiency Frontier · Click Dot for Replay'
            }
            actions={
              <div className="page-actions">
                <Button
                  mono
                  active={effectiveAxis === 'tokens'}
                  onClick={() => setFrontierAxis('tokens')}
                >
                  Tokens / Game
                </Button>
                <Button
                  mono
                  active={effectiveAxis === 'usd'}
                  onClick={() => setFrontierAxis('usd')}
                >
                  USD / Game
                </Button>
                <Button
                  mono
                  active={frontierMode === 'table'}
                  onClick={() => setFrontierMode((m) => (m === 'chart' ? 'table' : 'chart'))}
                >
                  {frontierMode === 'chart' ? 'Show Table' : 'Show Plot'}
                </Button>
              </div>
            }
          >
            {frontierMode === 'table' ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Player</th>
                      <th>Kind</th>
                      <th>Input</th>
                      <th className="num">Cost / Game</th>
                      <th className="num">Cost / Solved Lvl</th>
                      <th className="num">Eff. Score</th>
                      <th className="num">Tokens In</th>
                      <th className="num">Tokens Out</th>
                    </tr>
                  </thead>
                  <tbody>
                    {collectionRows.map((r, i) => (
                      <tr key={`${r.player_id}-${r.effort ?? 'none'}-${r.collection}-${i}`}>
                        <td>
                          <span className="lb-player-cell">
                            <Swatch color={seriesColorFor(r, i)} />
                            <span>{rowLabel(r)}</span>
                          </span>
                        </td>
                        <td className="mono">{r.kind}</td>
                        <td className="mono">{rowModes(r)}</td>
                        <td className="num">{fmtUsd(r.cost_per_game)}</td>
                        <td className="num">{fmtUsd(r.cost_per_solved_level)}</td>
                        <td className="num">{fmtFloat(r.score, 3)}</td>
                        <td className="num">{fmtInt(r.tokens_in)}</td>
                        <td className="num">{fmtInt(r.tokens_out)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : frontierPoints.length === 0 ? (
              <Empty>No model compute/cost runs available for the log frontier.</Empty>
            ) : (
              <>
                <div className="lb-plot-box lb-plot-clickable" onClick={onScatterClick}>
                  <PlotFigure
                    deps={[frontierPoints, effectiveAxis, kpi.optScore, kpi.humanScore, kpi.randomScore, kpi.noopScore, collectionRows]}
                    make={(width) => {
                      const xs = frontierPoints.map((p) => p.xVal)
                      const minX = Math.min(...xs)
                      const maxX = Math.max(...xs)
                      const xMin = minX * 0.55
                      const xMax = maxX * 1.85

                      type LineStyle = 'solid' | 'long-dash' | 'dotted'
                      const rawRefs: Array<{ y: number; name: string; style: LineStyle }> = [
                        { y: kpi.optScore, name: 'optimal', style: 'solid' },
                      ]
                      if (kpi.humanScore != null) {
                        rawRefs.push({ y: kpi.humanScore, name: 'human', style: 'long-dash' })
                      }
                      if (kpi.randomScore != null) {
                        rawRefs.push({ y: kpi.randomScore, name: 'random', style: 'dotted' })
                      }
                      if (kpi.noopScore != null) {
                        rawRefs.push({ y: kpi.noopScore, name: 'noop', style: 'dotted' })
                      }
                      if (effectiveAxis === 'usd') {
                        for (const r of collectionRows) {
                          if (r.kind === 'model' && (r.cost_per_game == null || r.cost_per_game <= 0) && r.score > 0) {
                            rawRefs.push({ y: r.score, name: `${rowLabel(r)} [credits]`, style: 'long-dash' })
                          }
                        }
                      }

                      rawRefs.sort((a, b) => b.y - a.y)
                      const refLines: Array<{ y: number; label: string; style: LineStyle }> = []
                      for (const item of rawRefs) {
                        const prev = refLines[refLines.length - 1]
                        if (prev && Math.abs(prev.y - item.y) < 0.038) {
                          const baseNames = prev.label.replace(/\s*\([0-9.]+\)$/, '')
                          prev.label = `${baseNames} / ${item.name} (${prev.y.toFixed(3)})`
                        } else {
                          refLines.push({
                            y: item.y,
                            label: `${item.name} (${item.y.toFixed(3)})`,
                            style: item.style,
                          })
                        }
                      }

                      const solidRefs = refLines.filter((r) => r.style === 'solid')
                      const dashRefs = refLines.filter((r) => r.style === 'long-dash')
                      const dotRefs = refLines.filter((r) => r.style === 'dotted')

                      const primaryLabelPoints = frontierPoints.filter((_, idx) => !(idx % 2 === 1 && frontierPoints[idx]?.score === 0))
                      const staggeredLabelPoints = frontierPoints.filter((_, idx) => idx % 2 === 1 && frontierPoints[idx]?.score === 0)

                      return {
                        width,
                        height: 245,
                        marginRight: 156,
                        marginBottom: 38,
                        x: {
                          type: 'log',
                          domain: [xMin, xMax],
                          label:
                            effectiveAxis === 'usd'
                              ? 'Cost per game (USD, log scale)'
                              : 'Total tokens per game (in + out, log scale)',
                          tickFormat: (d: number) =>
                            effectiveAxis === 'usd'
                              ? `$${d < 0.01 ? d.toFixed(3) : d.toFixed(2)}`
                              : fmtTokensCompact(d),
                        },
                        y: {
                          domain: [0, 1.06],
                          label: 'Action-efficiency score',
                        },
                        marks: [
                          Plot.ruleY(solidRefs, {
                            y: 'y',
                            stroke: cssVar('--text-2'),
                            strokeWidth: 1,
                          }),
                          Plot.ruleY(dashRefs, {
                            y: 'y',
                            stroke: cssVar('--text-2'),
                            strokeDasharray: '9,5',
                          }),
                          Plot.ruleY(dotRefs, {
                            y: 'y',
                            stroke: cssVar('--text-3'),
                            strokeDasharray: '2,4',
                          }),
                          Plot.text(refLines, {
                            x: xMax,
                            y: 'y',
                            text: 'label',
                            textAnchor: 'start',
                            dx: 6,
                            fill: cssVar('--text-2'),
                          }),
                          Plot.dot(frontierPoints, {
                            x: 'xVal',
                            y: 'score',
                            fill: (d: (typeof frontierPoints)[number]) => d.color,
                            stroke: cssVar('--surface-1'),
                            strokeWidth: 2,
                            r: 7,
                            tip: true,
                            title: (d: (typeof frontierPoints)[number]) =>
                              `${d.label} [${rowModes(d.row)}]\nScore: ${d.score.toFixed(3)}\nSolve rate: ${(d.row.level_solve_rate * 100).toFixed(1)}%\nTokens/game: ${fmtTokensCompact(d.tokensPerGame)}${d.cost != null ? `\nCost/game: $${d.cost.toFixed(4)}` : '\nCost/game: sponsored GPU credits'}${d.runId ? '\nClick dot to open best replay →' : ''}`,
                          }),
                          Plot.text(primaryLabelPoints, {
                            x: 'xVal',
                            y: 'score',
                            text: 'label',
                            dy: -12,
                            fill: cssVar('--text-1'),
                          }),
                          Plot.text(staggeredLabelPoints, {
                            x: 'xVal',
                            y: 'score',
                            text: 'label',
                            dy: -24,
                            fill: cssVar('--text-1'),
                          }),
                        ],
                      }
                    }}
                  />
                </div>
                <div className="lb-ref-legend mono">
                  <span>
                    <span className="lb-line-sample lb-line-solid" /> optimal ({fmtFloat(kpi.optScore, 3)})
                  </span>
                  {kpi.humanScore != null && (
                    <span>
                      <span className="lb-line-sample lb-line-dash" /> human ({fmtFloat(kpi.humanScore, 3)})
                    </span>
                  )}
                  <span>
                    <span className="lb-line-sample lb-line-dot" /> random / noop ({fmtFloat(kpi.randomScore ?? 0, 3)} / {fmtFloat(kpi.noopScore ?? 0, 3)})
                  </span>
                </div>
              </>
            )}
          </Panel>

          <Panel
            label="Benchmark Ledger"
            actions={<span className="mono muted">{sortedRows.length} rows · click column headers to sort</span>}
          >
            <div className="table-wrap">
              <table className="table lb-ledger-table">
                <thead>
                  <tr className="lb-group-row">
                    <th colSpan={4} className="lb-group-th">ENTITY &amp; MODALITY</th>
                    <th colSpan={4 + holdoutCols} className="lb-group-th lb-group-sep">OUTCOME</th>
                    <th colSpan={3} className="lb-group-th lb-group-sep">EFFICIENCY</th>
                    <th colSpan={4} className="lb-group-th lb-group-sep">BEHAVIOUR</th>
                  </tr>
                  <tr>
                    <th>Player</th>
                    <th>Kind</th>
                    <th>Input</th>
                    <th>Harness</th>
                    <th className="num lb-group-sep">Games</th>
                    <th className="num">
                      <button className={cx('lb-sort-btn', sortKey === 'score' && 'active')} onClick={() => handleSort('score')}>
                        Score{sortArrow('score')}
                      </button>
                    </th>
                    {hasHoldout && <th className="num">Seen</th>}
                    {hasHoldout && <th className="num">Unseen Pair</th>}
                    {hasHoldout && <th className="num">Unseen Skin</th>}
                    <th className="num">
                      <button className={cx('lb-sort-btn', sortKey === 'level_solve_rate' && 'active')} onClick={() => handleSort('level_solve_rate')}>
                        Lvl Solve{sortArrow('level_solve_rate')}
                      </button>
                    </th>
                    <th className="num">
                      <button className={cx('lb-sort-btn', sortKey === 'game_win_rate' && 'active')} onClick={() => handleSort('game_win_rate')}>
                        Game Win{sortArrow('game_win_rate')}
                      </button>
                    </th>
                    <th className="num lb-group-sep">
                      <button className={cx('lb-sort-btn', sortKey === 'median_actions' && 'active')} onClick={() => handleSort('median_actions')}>
                        Med Act{sortArrow('median_actions')}
                      </button>
                    </th>
                    <th className="num">
                      <button className={cx('lb-sort-btn', sortKey === 'cost_per_game' && 'active')} onClick={() => handleSort('cost_per_game')}>
                        Cost/Game{sortArrow('cost_per_game')}
                      </button>
                    </th>
                    <th className="num">
                      <button className={cx('lb-sort-btn', sortKey === 'latency_ms_median' && 'active')} onClick={() => handleSort('latency_ms_median')}>
                        Latency{sortArrow('latency_ms_median')}
                      </button>
                    </th>
                    <th className="num lb-group-sep">
                      <button className={cx('lb-sort-btn', sortKey === 'resets_total' && 'active')} onClick={() => handleSort('resets_total')}>
                        Resets{sortArrow('resets_total')}
                      </button>
                    </th>
                    <th className="num">
                      <button className={cx('lb-sort-btn', sortKey === 'no_effect_rate' && 'active')} onClick={() => handleSort('no_effect_rate')}>
                        No-Effect{sortArrow('no_effect_rate')}
                      </button>
                    </th>
                    <th className="num">
                      <button className={cx('lb-sort-btn', sortKey === 'belief_accuracy' && 'active')} onClick={() => handleSort('belief_accuracy')}>
                        Belief{sortArrow('belief_accuracy')}
                      </button>
                    </th>
                    <th className="num">Trace</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row, idx) => {
                    const color = seriesColorFor(row, idx)
                    const prov = rowProvider(row)
                    const bestRunId = resolveBestRun(row)
                    const bestScore = bestValues.score != null && Math.abs(row.score - bestValues.score) < 1e-6
                    const bestSolve =
                      bestValues.level_solve_rate != null &&
                      Math.abs(row.level_solve_rate - bestValues.level_solve_rate) < 1e-6
                    const bestWin =
                      bestValues.game_win_rate != null &&
                      Math.abs(row.game_win_rate - bestValues.game_win_rate) < 1e-6
                    const bestMedAct =
                      row.median_actions != null &&
                      bestValues.median_actions != null &&
                      Math.abs(row.median_actions - bestValues.median_actions) < 1e-6
                    const bestCost =
                      row.cost_per_game != null &&
                      bestValues.cost_per_game != null &&
                      Math.abs(row.cost_per_game - bestValues.cost_per_game) < 1e-6
                    const bestLat =
                      row.latency_ms_median != null &&
                      bestValues.latency_ms_median != null &&
                      Math.abs(row.latency_ms_median - bestValues.latency_ms_median) < 1e-6
                    const bestResets =
                      row.resets_total != null &&
                      bestValues.resets_total != null &&
                      Math.abs(row.resets_total - bestValues.resets_total) < 1e-6
                    const bestNoEff =
                      row.no_effect_rate != null &&
                      bestValues.no_effect_rate != null &&
                      Math.abs(row.no_effect_rate - bestValues.no_effect_rate) < 1e-6
                    const bestBelief =
                      row.belief_accuracy != null &&
                      bestValues.belief_accuracy != null &&
                      Math.abs(row.belief_accuracy - bestValues.belief_accuracy) < 1e-6

                    return (
                      <tr key={`${row.player_id}-${row.effort ?? 'none'}-${row.collection}-${row.harness_version ?? 'h1'}`}>
                        <td>
                          <div className="lb-player-stack">
                            <div className="lb-player-cell">
                              <Swatch color={color} />
                              <span>{rowLabel(row)}</span>
                              {row.subset_note && (
                                <span className="lb-tag" title={row.subset_note}>
                                  subset
                                </span>
                              )}
                            </div>
                            {prov && <span className="lb-provider mono">{prov}</span>}
                          </div>
                        </td>
                        <td className="mono">{row.tier || row.kind}</td>
                        <td className="mono">{rowModes(row)}</td>
                        <td className="mono">{row.harness_version || '—'}</td>
                        <td className="num lb-group-sep">{row.games}</td>
                        <td className={cx('num', 'lb-score-td', bestScore && 'lb-best')}>
                          <div className="lb-score-wrap">
                            <span>{fmtFloat(row.score, 3)}</span>
                            <div className="lb-score-track" aria-hidden="true">
                              <div
                                className="lb-score-fill"
                                style={{
                                  width: `${Math.max(0, Math.min(100, row.score * 100))}%`,
                                  background: color,
                                }}
                              />
                            </div>
                          </div>
                        </td>
                        {hasHoldout && <td className="num">{fmtFloat(row.seen_score, 3)}</td>}
                        {hasHoldout && <td className="num">{fmtFloat(row.unseen_pair_score, 3)}</td>}
                        {hasHoldout && <td className="num">{fmtFloat(row.unseen_skin_score, 3)}</td>}
                        <td className={cx('num', bestSolve && 'lb-best')}>
                          {fmtPct(row.level_solve_rate)}
                        </td>
                        <td className={cx('num', bestWin && 'lb-best')}>
                          {fmtPct(row.game_win_rate)}
                        </td>
                        <td className={cx('num', 'lb-group-sep', bestMedAct && 'lb-best')}>
                          {fmtInt(row.median_actions)}
                        </td>
                        <td className={cx('num', bestCost && 'lb-best')}>
                          <span className="lb-cost-cell">
                            <span>{fmtUsd(row.cost_per_game)}</span>
                            {row.cost_underreported && (
                              <span
                                className="lb-tag lb-tag-warn"
                                title={
                                  row.cost_note ||
                                  'Pre-17:15 Gemini run: thinking tokens excluded from completion_tokens; true API cost ~3.6x higher.'
                                }
                              >
                                ~3.6× low
                              </span>
                            )}
                          </span>
                        </td>
                        <td className={cx('num', bestLat && 'lb-best')}>
                          {row.latency_ms_median != null ? `${Math.round(row.latency_ms_median)} ms` : '—'}
                        </td>
                        <td className={cx('num', 'lb-group-sep', bestResets && 'lb-best')}>
                          {row.resets_total ?? '—'}
                        </td>
                        <td className={cx('num', bestNoEff && 'lb-best')}>
                          {fmtPct(row.no_effect_rate)}
                        </td>
                        <td className={cx('num', bestBelief && 'lb-best')}>
                          {fmtPct(row.belief_accuracy)}
                        </td>
                        <td className="num mono">
                          {bestRunId ? (
                            <Link to={`/replay/${encodeURIComponent(bestRunId)}`} className="lb-replay-pill">
                              #{bestRunId.slice(-6)} →
                            </Link>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="lb-subset-note mono">
              Modality note: harness h1 sends lossless 64×64 run-length grids (rle) to all models plus PNG frames (image+rle) to vision-capable models.
              {sortedRows.some((r) => r.subset_note) && (
                <>
                  {' · '}Subset evaluations:{' '}
                  {sortedRows
                    .filter((r) => r.subset_note)
                    .map((r) => `${rowLabel(r)}: ${r.subset_note}`)
                    .join(' · ')}
                </>
              )}
            </div>
          </Panel>

          <div className="lb-two-col">
            <Panel
              label="Thinking-Effort Ablation"
              actions={
                effortSeries.length > 0 && (
                  <Button
                    mono
                    active={effortMode === 'table'}
                    onClick={() => setEffortMode((m) => (m === 'chart' ? 'table' : 'chart'))}
                  >
                    {effortMode === 'chart' ? 'Show Table' : 'Show Plot'}
                  </Button>
                )
              }
            >
              {effortSeries.length === 0 ? (
                <Empty>
                  Effort ablation compares a single model across multiple reasoning budgets (low → medium → high). Currently only single-effort rows are loaded for this collection.
                </Empty>
              ) : effortMode === 'table' ? (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Model</th>
                        <th>Effort</th>
                        <th className="num">Score</th>
                        <th className="num">Cost / Game</th>
                      </tr>
                    </thead>
                    <tbody>
                      {effortSeries.map((pt) => (
                        <tr key={`${pt.player_id}-${pt.effort}`}>
                          <td>{pt.label}</td>
                          <td className="mono">{pt.effort}</td>
                          <td className="num">{fmtFloat(pt.score, 3)}</td>
                          <td className="num">{fmtUsd(pt.cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <PlotFigure
                  deps={[effortSeries]}
                  make={(width) => ({
                    width,
                    height: 220,
                    marginBottom: 34,
                    x: {
                      label: 'Reasoning effort',
                      domain: ['low', 'medium', 'high', 'xhigh', 'max'].filter((e) =>
                        effortSeries.some((p) => p.effort === e),
                      ),
                    },
                    y: { domain: [0, 1], label: 'Action-efficiency score' },
                    color: { legend: true, range: seriesColors() },
                    marks: [
                      Plot.lineY(effortSeries, {
                        x: 'effort',
                        y: 'score',
                        stroke: 'label',
                        strokeWidth: 2,
                      }),
                      Plot.dot(effortSeries, {
                        x: 'effort',
                        y: 'score',
                        fill: 'label',
                        stroke: cssVar('--surface-1'),
                        strokeWidth: 2,
                        r: 6,
                        tip: true,
                      }),
                    ],
                  })}
                />
              )}
            </Panel>

            <Panel label="Evaluated Model Cards &amp; Baselines">
              {registeredCards.length === 0 ? (
                <Empty>Only reference baselines are present in this collection.</Empty>
              ) : (
                <div className="lb-model-list">
                  {registeredCards.map(({ row, color }) => {
                    const card = row.model
                    return (
                      <div key={row.player_id} className="lb-model-card">
                        <div className="lb-player-cell">
                          <Swatch color={color} />
                          <strong>{row.display_name || row.player_id}</strong>
                          <span className="lb-tag">{card?.tier || row.kind}</span>
                        </div>
                        <div className="lb-model-meta mono">
                          <span>id: {row.player_id}</span>
                          <span>provider: {card?.provider || row.provider || '—'}</span>
                          <span>input: {rowModes(row)}</span>
                          <span>effort: {row.effort || card?.default_effort || '—'}</span>
                        </div>
                        <div className="lb-model-meta mono">
                          <span>solved: {row.levels_solved}/{row.levels_attempted}</span>
                          <span>rhae vs human: {row.rhae_vs_human != null ? fmtFloat(row.rhae_vs_human, 3) : 'pending human'}</span>
                          {row.seen_score != null && <span>seen: {fmtFloat(row.seen_score, 3)}</span>}
                          {row.unseen_pair_score != null && <span>unseen pair: {fmtFloat(row.unseen_pair_score, 3)}</span>}
                          {row.unseen_skin_score != null && <span>unseen skin: {fmtFloat(row.unseen_skin_score, 3)}</span>}
                        </div>
                        {(card?.params || card?.notes) && (
                          <span className="muted">{[card?.params, card?.notes].filter(Boolean).join(' · ')}</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}
