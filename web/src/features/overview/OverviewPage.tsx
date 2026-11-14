import * as Plot from '@observablehq/plot'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { PALETTE } from '@/lib/palette'
import { PlotFigure, seriesColors, cssVar } from '@/lib/PlotFigure'
import type { Frame, RunMeta } from '@/lib/types'
import type { LeaderboardDocument, LeaderboardRow } from '@/features/leaderboard/types'
import { completionCompare } from '@/features/leaderboard/ranking'
import { XrayOverlay } from '@/features/play/XrayOverlay'
import { Button, Empty, ErrorState, Panel, Swatch } from '@/design/primitives'
import './overview.css'

const DEFAULT_COLLECTION = 'eval-v2'

/** Pick a run worth showing on the front page: the best finished model run, else the optimal baseline. */
function pickShowcase(runs: RunMeta[]): RunMeta | undefined {
  const done = runs.filter((r) => r.outcome && r.outcome !== 'IN_PROGRESS' && (r.actions ?? 0) > 5)
  const score = (r: RunMeta) =>
    (r.outcome === 'WIN' ? 1e6 : 0) + (r.levels_completed ?? 0) * 1e4 - (r.outcome === 'ABORTED' ? 1e5 : 0) - (r.actions ?? 0)
  const models = done.filter((r) => r.player?.kind === 'model').sort((a, b) => score(b) - score(a))
  return models[0] ?? done.find((r) => /optimal/.test(r.player?.name ?? '')) ?? done[0]
}

function rowSeriesColor(row: LeaderboardRow, idx: number): string {
  if (row.kind === 'baseline') return cssVar('--text-3') || '#76756f'
  const palette = seriesColors()
  const k = row.model_order != null && row.model_order < 900 ? Math.abs(row.model_order) % palette.length : idx % palette.length
  return palette[k] || cssVar('--accent') || '#ffdc00'
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  if (v > 0 && v < 0.01) return '<$0.01'
  return `$${v.toFixed(2)}`
}

function fmtTokensCompact(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v >= 10_000_000 ? 0 : 1)}M`
  if (v >= 1_000) return `${Math.round(v / 1_000)}k`
  return String(Math.round(v))
}

function rowLabel(row: LeaderboardRow, hideCollection = false): string {
  let base = row.display_name || row.model?.display_name || row.player_id
  if (hideCollection && row.collection) base = base.replace(` [${row.collection}]`, '')
  return row.effort ? `${base} (${row.effort})` : base
}

function Showcase({ run }: { run: RunMeta }) {
  const steps = useQuery({ queryKey: ['steps', run.run_id], queryFn: () => api.getRunSteps(run.run_id), staleTime: Infinity })
  const gameDesc = useQuery({
    queryKey: ['game', run.game_id],
    queryFn: () => api.getGame(run.game_id),
    staleTime: Infinity,
  })
  const [i, setI] = useState(0)
  const [xraySplit, setXraySplit] = useState<number | null>(null)
  const n = steps.data?.length ?? 0

  useEffect(() => {
    if (!n) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) return
    const t = setTimeout(() => setI((x) => (x + 1 >= n ? 0 : x + 1)), i + 1 >= n ? 2500 : 180)
    return () => clearTimeout(t)
  }, [i, n])

  const step = steps.data?.[i]
  const curLv = step?.truth?.level ?? 1
  const levelDesc = gameDesc.data?.levels?.find((l) => l.level === curLv) ?? null

  const recentFrames = useMemo(() => {
    const all = steps.data
    if (!all?.length) return []
    const out: Frame[] = []
    for (let k = Math.max(0, i - 5); k <= i; k++) {
      if ((all[k]?.truth?.level ?? 1) === curLv && all[k]?.frame) out.push(all[k].frame)
    }
    return out
  }, [steps.data, i, curLv])

  return (
    <figure className="ov-showcase">
      <div className="ov-showcase-head mono">
        <span className="muted">
          live playback · L{curLv} · step {i + 1}/{n || '?'}
        </span>
        <Button
          variant="ghost"
          mono
          active={xraySplit != null}
          onClick={() => setXraySplit((v) => (v == null ? 50 : null))}
        >
          x-ray {xraySplit != null ? `${xraySplit}%` : 'off'}
        </Button>
      </div>
      <div className="ov-canvas-center">
        <FrameCanvas
          frame={step?.frame}
          scale="fit"
          maxScale={6}
          bezel
          xraySplit={xraySplit}
          onXraySplitChange={setXraySplit}
          xrayOverlay={
            xraySplit != null ? (
              <XrayOverlay levelDesc={levelDesc} truth={step?.truth} recentFrames={recentFrames} />
            ) : undefined
          }
          label="A recorded run, playing back"
        />
      </div>
      <div className="ov-palette-strip" aria-label="16-colour game cartridge palette">
        {PALETTE.map((hex, idx) => (
          <span key={idx} style={{ background: hex }} title={`palette[${idx}] = ${hex}`} />
        ))}
      </div>
      <figcaption className="mono muted">
        <Link to={`/replay/${encodeURIComponent(run.run_id)}?step=${i}`}>
          {run.player?.name ?? run.player?.model_id}
        </Link>{' '}
        on {run.game_id}
        <span className="ov-hyp" title={step?.hypothesis ?? undefined}>{step?.hypothesis ? `“${step.hypothesis}”` : '\u00a0'}</span>
      </figcaption>
    </figure>
  )
}

const pct = (v?: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`)

export function OverviewPage() {
  const navigate = useNavigate()
  const games = useQuery({ queryKey: ['games', undefined], queryFn: () => api.listGames() })
  const runs = useQuery({ queryKey: ['runs', undefined, undefined], queryFn: () => api.listRuns() })
  const lb = useQuery({
    queryKey: ['derived', 'leaderboard'],
    queryFn: () => api.derived<LeaderboardDocument>('leaderboard'),
    retry: false,
  })

  const [frontierMode, setFrontierMode] = useState<'chart' | 'table'>('chart')
  const [frontierAxis, setFrontierAxis] = useState<'auto' | 'tokens' | 'usd'>('auto')

  const showcase = useMemo(() => pickShowcase(runs.data ?? []), [runs.data])

  const allRows = lb.data?.rows ?? []
  const hasEvalV2 = useMemo(() => allRows.some((r) => r.collection === DEFAULT_COLLECTION), [allRows])
  const collectionRows = useMemo(
    () => (hasEvalV2 ? allRows.filter((r) => r.collection === DEFAULT_COLLECTION) : allRows),
    [allRows, hasEvalV2],
  )

  // Front-page ranking shows real players only (models and humans). Baselines (optimal, random,
  // do-nothing, stop-early) are reference lines, not entries; they stay on the full leaderboard.
  const rows: LeaderboardRow[] = useMemo(
    () =>
      [...collectionRows]
        .filter((r) => r.kind !== 'baseline')
        .sort(completionCompare) // completion first: games won, levels solved, then efficiency
        .slice(0, 6),
    [collectionRows],
  )

  const refScores = useMemo(() => {
    const optRow = collectionRows.find((r) => r.player_id === 'optimal')
    const humanRow = collectionRows.find((r) => r.kind === 'human' || r.player_id === 'human')
    const randomRow = collectionRows.find((r) => r.player_id === 'random')
    const noopRow = collectionRows.find((r) => r.player_id === 'noop')
    return {
      optScore: optRow?.score ?? 1.0,
      humanScore: humanRow?.score ?? null,
      randomScore: randomRow?.score ?? null,
      noopScore: noopRow?.score ?? null,
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
            label: rowLabel(row, hasEvalV2),
            xVal,
            cost: row.cost_per_game ?? null,
            tokensPerGame,
            score: row.score,
            color: rowSeriesColor(row, idx),
            runId: row.best_run_id ?? null,
          }
        })
        .filter((pt) => pt.row.kind === 'model' && pt.xVal > 0),
    [collectionRows, effectiveAxis, hasEvalV2],
  )

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

  const firstGame = games.data?.[0]?.game_id

  return (
    <div className="ov">
      {games.error && runs.error ? (
        <ErrorState
          error={games.error}
          retry={() => {
            games.refetch()
            runs.refetch()
            lb.refetch()
          }}
        />
      ) : null}
      <section className="ov-top">
        <div className="ov-intro">
          <h1 className="ov-title">Games no model has seen before.</h1>
          <p className="ov-lede">
            Every game is generated and checked for a solution. Each level adds a new twist, and you discover what to do
            by trying moves on the board.
          </p>
          <ol className="ov-steps">
            <li>
              <span className="mono ov-n">1</span>
              <span>
                <b>New worlds.</b> Every game is generated and checked before you play.
              </span>
            </li>
            <li>
              <span className="mono ov-n">2</span>
              <span>
                <b>Learn by playing.</b> Watch the board and discover what each object does.
              </span>
            </li>
            <li>
              <span className="mono ov-n">3</span>
              <span>
                <b>Compare results.</b> See how your score stacks up against other players.
              </span>
            </li>
          </ol>
          <div className="ov-cta">
            <Link to="/challenge">
              <Button variant="primary">Take the challenge</Button>
            </Link>
            <Link to={firstGame ? `/play/${encodeURIComponent(firstGame)}` : '/play'}>
              <Button>Play a game</Button>
            </Link>
          </div>
        </div>
        <div className="ov-stage">{showcase ? <Showcase run={showcase} /> : <div className="ov-stage-empty" />}</div>
      </section>

      <div className="ov-bottom">
        <Panel label="leaderboard · top 6" pad={false} actions={<Link to="/leaderboard">full ledger →</Link>}>
          {rows.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>player</th>
                    <th className="num">games won</th>
                    <th className="num">levels won</th>
                    <th className="num">efficiency</th>
                    <th className="num">$/game</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const col = rowSeriesColor(r, i)
                    return (
                      <tr key={`${r.player_id}-${r.effort ?? ''}-${r.collection}`}>
                        <td className="num muted">{i + 1}</td>
                        <td>
                          <span className="ov-player-cell">
                            <Swatch color={col} />
                            <span>
                              {r.display_name ?? r.model?.display_name ?? r.player_id}
                              {r.effort && <span className="muted"> · {r.effort}</span>}
                              {r.kind !== 'model' && <span className="muted"> · {r.kind}</span>}
                              {r.collection && <span className="muted"> · {r.collection}</span>}
                            </span>
                          </span>
                        </td>
                        <td className="num">{pct(r.game_win_rate)}</td>
                        <td className="num">{pct(r.level_solve_rate)}</td>
                        <td className="num">
                          <div className="ov-score-cell">
                            <span>{r.score.toFixed(3)}</span>
                            <div className="ov-score-track" aria-hidden="true">
                              <div
                                className="ov-score-fill"
                                style={{
                                  width: `${Math.max(0, Math.min(100, r.score * 100))}%`,
                                  background: col,
                                }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="num">{r.cost_per_game ? `$${r.cost_per_game.toFixed(3)}` : '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted ov-pad">{lb.isLoading ? 'Loading…' : 'Leaderboard not built yet.'}</p>
          )}
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
                    <th className="num">Score</th>
                    <th className="num">Cost / Game</th>
                    <th className="num">Tokens / Game</th>
                  </tr>
                </thead>
                <tbody>
                  {frontierPoints.map((pt, i) => (
                    <tr key={`${pt.row.player_id}-${pt.row.effort ?? 'none'}-${i}`}>
                      <td>
                        <span className="ov-player-cell">
                          <Swatch color={pt.color} />
                          <span>{pt.label}</span>
                        </span>
                      </td>
                      <td className="num">{pt.score.toFixed(3)}</td>
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
            <div className="ov-plot-box" onClick={onScatterClick}>
              <PlotFigure
                deps={[
                  frontierPoints,
                  effectiveAxis,
                  refScores.optScore,
                  refScores.humanScore,
                  refScores.randomScore,
                  refScores.noopScore,
                  collectionRows,
                ]}
                make={(width) => {
                  const xs = frontierPoints.map((p) => p.xVal)
                  const minX = Math.min(...xs)
                  const maxX = Math.max(...xs)
                  const xMin = minX * 0.55
                  const xMax = maxX * 1.85

                  type LineStyle = 'solid' | 'long-dash' | 'dotted'
                  const rawRefs: Array<{ y: number; name: string; style: LineStyle }> = [
                    { y: refScores.optScore, name: 'optimal', style: 'solid' },
                  ]
                  if (refScores.humanScore != null) {
                    rawRefs.push({ y: refScores.humanScore, name: 'human', style: 'long-dash' })
                  }
                  if (refScores.randomScore != null) {
                    rawRefs.push({ y: refScores.randomScore, name: 'random', style: 'dotted' })
                  }
                  if (refScores.noopScore != null) {
                    rawRefs.push({ y: refScores.noopScore, name: 'noop', style: 'dotted' })
                  }
                  if (effectiveAxis === 'usd') {
                    for (const r of collectionRows) {
                      if (r.kind === 'model' && (r.cost_per_game == null || r.cost_per_game <= 0) && r.score > 0) {
                        rawRefs.push({ y: r.score, name: `${rowLabel(r, hasEvalV2)} (credits)`, style: 'long-dash' })
                      }
                    }
                  }

                  rawRefs.sort((a, b) => b.y - a.y)
                  const refLines: Array<{ y: number; label: string; style: LineStyle }> = []
                  for (const item of rawRefs) {
                    const prev = refLines[refLines.length - 1]
                    if (prev && Math.abs(prev.y - item.y) < 0.038) {
                      const baseNames = prev.label.replace(/\s+[0-9.]+$/, '')
                      prev.label = `${baseNames} / ${item.name} ${prev.y.toFixed(2)}`
                    } else {
                      refLines.push({
                        y: item.y,
                        label: `${item.name} ${item.y.toFixed(2)}`,
                        style: item.style,
                      })
                    }
                  }

                  const solidRefs = refLines.filter((r) => r.style === 'solid')
                  const dashRefs = refLines.filter((r) => r.style === 'long-dash')
                  const dotRefs = refLines.filter((r) => r.style === 'dotted')

                  const height = 260
                  const mL = 44
                  const mR = 112
                  const mT = 20
                  const mB = 38
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
                      label: 'Score',
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
      </div>
    </div>
  )
}
