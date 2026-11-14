import * as Plot from '@observablehq/plot'
import { useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Button,
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
import { PlotFigure, cssVar } from '@/lib/PlotFigure'
import { playerColor } from '@/lib/modelColors'
import type { RunMeta } from '@/lib/types'
import { fetchLeaderboardH2, fetchLeaderboardH2b } from './phase2Api'
import { ModelCardDialog } from './ModelCardDialog'
import { bestByCompletion, completionCompare } from './ranking'
import { LeaderboardH2View } from './PostTrainingSection'
import type { LeaderboardDocument, LeaderboardRow } from './types'
import './leaderboard.css'

type BoardView = 'h1' | 'h2' | 'h2b'

type SortKey = 'score' | 'level_solve_rate' | 'game_win_rate' | 'median_actions' | 'cost_per_game'

const SORT_KEYS: SortKey[] = ['score', 'level_solve_rate', 'game_win_rate', 'median_actions', 'cost_per_game']

type KindFilter = 'all' | 'model' | 'human'

const DEFAULT_COLLECTION = 'eval-v2'

const HIGHER_IS_BETTER = new Set<SortKey>(['score', 'level_solve_rate', 'game_win_rate'])

/** "Evaluated on 8/23 games in eval-v2 · …" -> "8/23" */
function subsetCoverage(note: string | null | undefined): string | null {
  const m = note?.match(/(\d+\/\d+)\s+games/)
  return m ? m[1] : null
}

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
  if (v > 0 && v < 0.01) return '<$0.01'
  return `$${v.toFixed(2)}`
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

function rowLabel(row: LeaderboardRow, hideCollection = false): string {
  let base = row.display_name || row.model?.display_name || row.player_id
  if (hideCollection) base = base.replace(` [${row.collection}]`, '')
  return row.effort ? `${base} (${row.effort})` : base
}

/** Row colour: the player's fixed colour, the same on every page (see lib/modelColors.ts). */
export function rowColor(row: LeaderboardRow): string {
  return playerColor({ kind: row.kind, id: row.player_id })
}

/** Kept for callers that build a per-view lookup; colours no longer depend on the rows shown. */
export function buildRowColorMap(_rows: LeaderboardRow[]): (row: LeaderboardRow) => string {
  return rowColor
}

export function seriesColorFor(row: LeaderboardRow, _fallbackIndex?: number): string {
  return rowColor(row)
}

function runRankScore(r: RunMeta): number {
  return (r.outcome === 'WIN' ? 1e7 : 0) + (r.levels_completed ?? 0) * 1e4 - (r.actions ?? 0)
}

export function LeaderboardPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawView = searchParams.get('view')
  const view: BoardView = rawView === 'h2' || rawView === 'h2b' ? rawView : 'h1'

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
  const lbH2b = useQuery({
    queryKey: ['derived', 'leaderboard_h2b'],
    queryFn: fetchLeaderboardH2b,
  })
  const runsQ = useQuery({
    queryKey: ['runs', 'lb-best-lookup'],
    queryFn: () => api.listRuns(),
    staleTime: 60_000,
  })

  const [collectionPick, setCollection] = useState<string | null>(null)
  const [kindFilter, setKindFilter] = useState<KindFilter>('all')
  const [sortKey, setSortKey] = useState<SortKey>('game_win_rate')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [frontierMode, setFrontierMode] = useState<'chart' | 'table'>('chart')
  const [frontierAxis, setFrontierAxis] = useState<'auto' | 'tokens' | 'usd'>('auto')
  const [cardRow, setCardRow] = useState<LeaderboardRow | null>(null)

  const allRows = (lb.data?.rows ?? []).filter((row) => row.kind !== 'baseline')

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

  const collection =
    collectionPick ?? (collections.includes(DEFAULT_COLLECTION) ? DEFAULT_COLLECTION : 'all')

  const collectionRows = useMemo(() => {
    if (collection === 'all') return allRows
    return allRows.filter((r) => r.collection === collection)
  }, [allRows, collection])

  const colorForRow = useMemo(() => buildRowColorMap(collectionRows), [collectionRows])

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
      if (cmp === 0) return completionCompare(a, b) // ties: completion first (ranking.ts)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [filteredRows, sortKey, sortDir])

  const bestValues = useMemo(() => {
    const out: Partial<Record<SortKey, number>> = {}
    for (const k of SORT_KEYS) {
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
    const bestModel = bestByCompletion(modelRows)
    const humanRow = collectionRows.find((r) => r.kind === 'human' || r.player_id === 'human')
    const totalGames = collectionRows.reduce((acc, r) => acc + (r.games || 0), 0)

    return {
      totalGames,
      modelCount: modelRows.length,
      bestModel,
      humanRow: humanRow ?? null,
      humanScore: humanRow?.score ?? null, // efficiency reference line in the cost chart
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
        .map((row) => {
          const totalTokens = (row.tokens_in ?? 0) + (row.tokens_out ?? 0)
          const tokensPerGame = row.games > 0 ? totalTokens / row.games : 0
          const xVal = effectiveAxis === 'usd' ? (row.cost_per_game ?? 0) : tokensPerGame
          return {
            row,
            label: rowLabel(row, collection !== 'all'),
            xVal,
            cost: row.cost_per_game ?? null,
            tokensPerGame,
            score: row.score,
            color: colorForRow(row),
            runId: bestRunByPlayer.get(`${row.player_id}::${row.effort ?? ''}`) ?? bestRunByPlayer.get(row.player_id) ?? null,
          }
        })
        .filter((pt) => pt.row.kind === 'model' && pt.xVal > 0),
    [collectionRows, collection, effectiveAxis, bestRunByPlayer, colorForRow],
  )

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

  const sortTh = (key: SortKey, label: string) => (
    <th className="num">
      <button className={cx('lb-sort-btn', sortKey === key && 'active')} onClick={() => handleSort(key)}>
        {label}
        {sortArrow(key)}
      </button>
    </th>
  )

  const isBest = (row: LeaderboardRow, key: SortKey) => {
    const v = row[key]
    const best = bestValues[key]
    return typeof v === 'number' && best != null && Math.abs(v - best) < 1e-6
  }

  return (
    <div className="lb-stack">
      <PageHeader title="Leaderboard" />

      <div className="lb-view-tabs" role="tablist" aria-label="Leaderboard views">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'h1'}
          className={cx('lb-view-tab', view === 'h1' && 'active')}
          onClick={() => setView('h1')}
        >
          <span>Standard</span>
          <span className="lb-tab-count">{allRows.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'h2'}
          className={cx('lb-view-tab', view === 'h2' && 'active')}
          onClick={() => setView('h2')}
        >
          <span>Extended</span>
          <span className="lb-tab-count">{lbH2.data?.rows.length ?? '—'}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'h2b'}
          className={cx('lb-view-tab', view === 'h2b' && 'active')}
          onClick={() => setView('h2b')}
          title="Extended harness, up to 5 moves per model call"
        >
          <span>Extended, multi-move</span>
          <span className="lb-tab-count">{lbH2b.data?.rows.length ?? '—'}</span>
        </button>
      </div>

      {view === 'h2' || view === 'h2b' ? (
        <LeaderboardH2View
          doc={view === 'h2' ? lbH2.data : lbH2b.data}
          isLoading={view === 'h2' ? lbH2.isLoading : lbH2b.isLoading}
          resolveRunFallback={resolveBestRun}
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
                label="Best Model"
                value={kpi.bestModel ? `${Math.round((kpi.bestModel.game_win_rate ?? 0) * 100)}%` : '—'}
                sub={kpi.bestModel ? `games won · ${rowLabel(kpi.bestModel, collection !== 'all')}` : undefined}
              />
            </div>
            <div className="lb-kpi-cell">
              <Stat
                label="Human"
                value={kpi.humanRow ? `${Math.round((kpi.humanRow.game_win_rate ?? 0) * 100)}%` : '—'}
                sub="games won"
              />
            </div>
            <div className="lb-kpi-cell">
              <Stat label="Games Evaluated" value={kpi.totalGames} sub={`${kpi.modelCount} models`} />
            </div>
          </div>

          <div className="lb-controls">
            <div className="lb-filter-group">
              <span className="kicker lb-filter-label">Collection</span>
              {collections.map((c) => (
                <Button key={c} mono active={collection === c} onClick={() => setCollection(c)}>
                  {c}
                </Button>
              ))}
            </div>
            <div className="lb-filter-group">
              <span className="kicker lb-filter-label">Player</span>
              {(['all', 'model', 'human'] as KindFilter[]).map((k) => (
                <Button key={k} mono active={kindFilter === k} onClick={() => setKindFilter(k)}>
                  {k}
                </Button>
              ))}
            </div>
          </div>

          <Panel
            label="Leaderboard"
            actions={<span className="mono muted">click a name for its model card</span>}
          >
            <div className="table-wrap">
              <table className="table lb-ledger-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th className="num">Games</th>
                    {sortTh('game_win_rate', 'Games Won')}
                    {sortTh('level_solve_rate', 'Levels Won')}
                    {sortTh('score', 'Efficiency')}
                    {sortTh('median_actions', 'Med. Actions')}
                    {sortTh('cost_per_game', 'Cost / Game')}
                    <th className="num">Replay</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row) => {
                    const color = colorForRow(row)
                    const bestRunId = resolveBestRun(row)
                    const coverage = subsetCoverage(row.subset_note)
                    return (
                      <tr
                        key={`${row.player_id}-${row.effort ?? 'none'}-${row.collection}-${row.harness_version ?? 'h1'}`}
                        className={row.kind === 'human' ? 'lb-human-row' : undefined}
                        aria-label={row.kind === 'human' ? 'Human result' : undefined}
                      >
                        <td>
                          <button type="button" className="lb-name-btn" onClick={() => setCardRow(row)}>
                            <Swatch color={color} />
                            <span>{rowLabel(row, collection !== 'all')}</span>
                          </button>
                        </td>
                        <td className="num" title={row.subset_note ?? undefined}>
                          {coverage ?? row.games}
                        </td>
                        <td className={cx('num', isBest(row, 'game_win_rate') && 'lb-best')}>
                          {fmtPct(row.game_win_rate)}
                        </td>
                        <td className={cx('num', isBest(row, 'level_solve_rate') && 'lb-best')}>
                          {fmtPct(row.level_solve_rate)}
                        </td>
                        <td className={cx('num', 'lb-score-td', isBest(row, 'score') && 'lb-best')}>
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
                        <td className={cx('num', isBest(row, 'median_actions') && 'lb-best')}>
                          {fmtInt(row.median_actions)}
                        </td>
                        <td className={cx('num', isBest(row, 'cost_per_game') && 'lb-best')}>
                          <span
                            className="lb-cost-cell"
                            title={
                              row.cost_underreported
                                ? row.cost_note ||
                                  'Thinking tokens excluded from this run; true API cost ~3.6x higher.'
                                : undefined
                            }
                          >
                            {fmtUsd(row.cost_per_game)}
                          </span>
                        </td>
                        <td className="num mono">
                          {bestRunId ? (
                            <Link to={`/replay/${encodeURIComponent(bestRunId)}`} className="lb-replay-pill">
                              ▶
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
          </Panel>

          <Panel
            label={effectiveAxis === 'tokens' ? 'Score vs Tokens / Game' : 'Score vs Cost / Game'}
            actions={
              <div className="page-actions">
                <Button mono active={effectiveAxis === 'tokens'} onClick={() => setFrontierAxis('tokens')}>
                  Tokens
                </Button>
                <Button mono active={effectiveAxis === 'usd'} onClick={() => setFrontierAxis('usd')}>
                  USD
                </Button>
                <Button
                  mono
                  active={frontierMode === 'table'}
                  onClick={() => setFrontierMode((m) => (m === 'chart' ? 'table' : 'chart'))}
                >
                  {frontierMode === 'chart' ? 'Table' : 'Plot'}
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
                      <th className="num">Efficiency</th>
                      <th className="num">Cost / Game</th>
                      <th className="num">Tokens / Game</th>
                    </tr>
                  </thead>
                  <tbody>
                    {frontierPoints.map((pt, i) => (
                      <tr key={`${pt.row.player_id}-${pt.row.effort ?? 'none'}-${i}`}>
                        <td>
                          <span className="lb-player-cell">
                            <Swatch color={pt.color} />
                            <span>{pt.label}</span>
                          </span>
                        </td>
                        <td className="num">{fmtFloat(pt.score, 3)}</td>
                        <td className="num">{fmtUsd(pt.cost)}</td>
                        <td className="num">{fmtTokensCompact(pt.tokensPerGame)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : frontierPoints.length === 0 ? (
              <Empty>No model cost data for this collection.</Empty>
            ) : (
                <div className="lb-plot-box lb-plot-clickable" onClick={onScatterClick}>
                  <PlotFigure
                    deps={[frontierPoints, effectiveAxis, kpi.humanScore, kpi.humanRow, collectionRows, colorForRow]}
                    make={(width) => {
                      const xs = frontierPoints.map((p) => p.xVal)
                      const minX = Math.min(...xs)
                      const maxX = Math.max(...xs)
                      const xMin = minX * 0.55
                      const xMax = maxX * 1.85

                      type LineStyle = 'solid' | 'long-dash' | 'dotted'
                      const rawRefs: Array<{ y: number; name: string; style: LineStyle; color?: string }> = []
                      if (kpi.humanScore != null) {
                        rawRefs.push({
                          y: kpi.humanScore,
                          name: 'human',
                          style: 'long-dash',
                          color: kpi.humanRow ? colorForRow(kpi.humanRow) : undefined,
                        })
                      }
                      if (effectiveAxis === 'usd') {
                        for (const r of collectionRows) {
                          if (r.kind === 'model' && (r.cost_per_game == null || r.cost_per_game <= 0) && r.score > 0) {
                            rawRefs.push({
                              y: r.score,
                              name: `${rowLabel(r, collection !== 'all')} (credits)`,
                              style: 'long-dash',
                              color: colorForRow(r),
                            })
                          }
                        }
                      }

                      rawRefs.sort((a, b) => b.y - a.y)
                      const refLines: Array<{ y: number; label: string; style: LineStyle; color?: string }> = []
                      for (const item of rawRefs) {
                        const prev = refLines[refLines.length - 1]
                        if (prev && Math.abs(prev.y - item.y) < 0.038) {
                          const baseNames = prev.label.replace(/\s+[0-9.]+$/, '')
                          prev.label = `${baseNames} / ${item.name} ${prev.y.toFixed(2)}`
                          if (!prev.color && item.color) prev.color = item.color
                        } else {
                          refLines.push({
                            y: item.y,
                            label: `${item.name} ${item.y.toFixed(2)}`,
                            style: item.style,
                            color: item.color,
                          })
                        }
                      }

                      const solidRefs = refLines.filter((r) => r.style === 'solid')
                      const dashRefs = refLines.filter((r) => r.style === 'long-dash')
                      const dotRefs = refLines.filter((r) => r.style === 'dotted')

                      // Layout in pixels so labels can be placed without overlapping each other or the dots.
                      const height = 280
                      const mL = 44
                      const mR = 118
                      const mT = 24
                      const mB = 40
                      const innerW = width - mL - mR
                      const innerH = height - mT - mB
                      const yMax = 1.06
                      const lnMin = Math.log(xMin)
                      const lnMax = Math.log(xMax)
                      const px = (x: number) => mL + ((Math.log(x) - lnMin) / (lnMax - lnMin)) * innerW
                      const py = (y: number) => mT + (1 - y / yMax) * innerH
                      const dataX = (p: number) => Math.exp(lnMin + ((p - mL) / innerW) * (lnMax - lnMin))
                      const dataY = (p: number) => yMax * (1 - (p - mT) / innerH)

                      const sameEffort = new Set(frontierPoints.map((p) => p.row.effort ?? '')).size <= 1
                      const shortLabel = (p: (typeof frontierPoints)[number]) =>
                        sameEffort && p.row.effort ? p.label.replace(` (${p.row.effort})`, '') : p.label

                      type Anchor = 'start' | 'middle' | 'end'
                      type Box = { x0: number; x1: number; y0: number; y1: number }
                      const CANDIDATES: Array<[number, number, Anchor]> = [
                        [0, -14, 'middle'],
                        [0, 15, 'middle'],
                        [11, 0, 'start'],
                        [-11, 0, 'end'],
                        [8, -12, 'start'],
                        [-8, -12, 'end'],
                        [8, 13, 'start'],
                        [-8, 13, 'end'],
                        [0, -27, 'middle'],
                        [0, 28, 'middle'],
                      ]
                      const overlap = (a: Box, b: Box) =>
                        Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) *
                        Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0))
                      const dotBoxes: Box[] = frontierPoints.map((p) => ({
                        x0: px(p.xVal) - 8,
                        x1: px(p.xVal) + 8,
                        y0: py(p.score) - 8,
                        y1: py(p.score) + 8,
                      }))
                      const placed: Box[] = []
                      const labels: Array<{ x: number; y: number; text: string; anchor: Anchor }> = []
                      const order = frontierPoints
                        .map((_, i) => i)
                        .sort((a, b) => frontierPoints[b].score - frontierPoints[a].score)
                      for (const i of order) {
                        const p = frontierPoints[i]
                        const text = shortLabel(p)
                        const w = text.length * 6 + 4
                        const cx0 = px(p.xVal)
                        const cy0 = py(p.score)
                        let best: { cost: number; x: number; y: number; anchor: Anchor; box: Box } | null = null
                        for (const [dx, dy, anchor] of CANDIDATES) {
                          const x = cx0 + dx
                          const y = cy0 + dy
                          const x0 = anchor === 'start' ? x : anchor === 'end' ? x - w : x - w / 2
                          const box = { x0, x1: x0 + w, y0: y - 6, y1: y + 6 }
                          let cost = 0
                          for (const b of placed) cost += overlap(box, b)
                          dotBoxes.forEach((b, j) => {
                            if (j !== i) cost += overlap(box, b)
                          })
                          if (box.x0 < mL || box.x1 > width - mR + 4) cost += 500
                          if (box.y0 < 2 || box.y1 > height - mB) cost += 500
                          if (!best || cost < best.cost) best = { cost, x, y, anchor, box }
                          if (cost === 0) break
                        }
                        // No free spot: leave the dot unlabeled (hover still names it) rather than overlap.
                        if (best && best.cost === 0) {
                          placed.push(best.box)
                          labels.push({ x: dataX(best.x), y: dataY(best.y), text, anchor: best.anchor })
                        }
                      }
                      const labelMark = (anchor: Anchor) =>
                        Plot.text(
                          labels.filter((l) => l.anchor === anchor),
                          { x: 'x', y: 'y', text: 'text', textAnchor: anchor, fill: cssVar('--text-1') },
                        )

                      return {
                        width,
                        height,
                        marginLeft: mL,
                        marginRight: mR,
                        marginTop: mT,
                        marginBottom: mB,
                        x: {
                          type: 'log',
                          domain: [xMin, xMax],
                          label: effectiveAxis === 'usd' ? 'Cost per game (USD, log)' : 'Tokens per game (log)',
                          tickFormat: (d: number) =>
                            effectiveAxis === 'usd'
                              ? `$${d < 0.01 ? d.toFixed(3) : d.toFixed(2)}`
                              : fmtTokensCompact(d),
                        },
                        y: {
                          domain: [0, yMax],
                          label: 'Efficiency',
                        },
                        marks: [
                          Plot.ruleY(solidRefs, {
                            y: 'y',
                            stroke: cssVar('--text-2'),
                            strokeWidth: 1,
                          }),
                          Plot.ruleY(dashRefs, {
                            y: 'y',
                            stroke: (d: (typeof refLines)[number]) => d.color ?? cssVar('--text-2'),
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
                            fill: (d: (typeof refLines)[number]) => d.color ?? cssVar('--text-2'),
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
                              [
                                d.label,
                                `Score ${d.score.toFixed(3)}`,
                                effectiveAxis === 'usd'
                                  ? d.cost != null
                                    ? `${fmtUsd(d.cost)} per game`
                                    : 'No USD price (GPU credits)'
                                  : `${fmtTokensCompact(d.tokensPerGame)} tokens per game`,
                                d.runId ? 'Click to watch replay' : null,
                              ]
                                .filter(Boolean)
                                .join('\n'),
                          }),
                          labelMark('middle'),
                          labelMark('start'),
                          labelMark('end'),
                        ],
                      }
                    }}
                  />
                </div>
            )}
          </Panel>
        </>
      )}

      {cardRow && (
        <ModelCardDialog
          row={cardRow}
          color={colorForRow(cardRow)}
          onClose={() => setCardRow(null)}
        />
      )}
    </div>
  )
}
