import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { PALETTE } from '@/lib/palette'
import { seriesColors, cssVar } from '@/lib/PlotFigure'
import type { Frame, RunMeta } from '@/lib/types'
import { useServerInfo } from '@/lib/server'
import type { LeaderboardDocument, LeaderboardRow } from '@/features/leaderboard/types'
import { XrayOverlay } from '@/features/play/XrayOverlay'
import { Button, Chip, ErrorState, Kbd, Panel, Stat, Swatch } from '@/design/primitives'
import './overview.css'

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
  const server = useServerInfo()
  const games = useQuery({ queryKey: ['games', undefined], queryFn: () => api.listGames() })
  const runs = useQuery({ queryKey: ['runs', undefined, undefined], queryFn: () => api.listRuns() })
  const lb = useQuery({
    queryKey: ['derived', 'leaderboard'],
    queryFn: () => api.derived<LeaderboardDocument>('leaderboard'),
    retry: false,
  })

  const showcase = useMemo(() => pickShowcase(runs.data ?? []), [runs.data])
  const ruleCount = useMemo(() => new Set((games.data ?? []).flatMap((g) => g.rules ?? [])).size, [games.data])
  const models = useMemo(
    () => new Set((runs.data ?? []).filter((r) => r.player?.kind === 'model').map((r) => r.player.model_id)).size,
    [runs.data],
  )
  const humans = useMemo(() => (runs.data ?? []).filter((r) => r.player?.kind === 'human').length, [runs.data])
  // Front-page ranking shows real players only (models and humans). Baselines (optimal, random,
  // do-nothing, stop-early) are reference lines, not entries; they stay on the full leaderboard.
  const rows: LeaderboardRow[] = useMemo(
    () =>
      [...(lb.data?.rows ?? [])]
        .filter((r) => r.kind !== 'baseline')
        .sort((a, b) => b.score - a.score)
        .slice(0, 6),
    [lb.data],
  )
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
            A factory that generates unlimited grid games, each one seeded, multi-level and proven solvable. Every level
            adds one new rule. Agents see only the 64×64 frame: no score, no rule names, no win flag. They have to work
            out the goal and the rules by acting, under a move budget.
          </p>
          <ol className="ov-steps">
            <li>
              <span className="mono ov-n">1</span>
              <span>
                <b>Factory.</b> Seeded generator, BFS solvability proof, budget from the optimal solution; every new
                rule is forced to matter.
              </span>
            </li>
            <li>
              <span className="mono ov-n">2</span>
              <span>
                <b>Pixels only.</b> Models and humans play identical frames via MCP, REST or keyboard — toggle X-Ray to
                contrast agent blindness against engine truth.
              </span>
            </li>
            <li>
              <span className="mono ov-n">3</span>
              <span>
                <b>Arena.</b> Frontier models, humans and baselines on held-out worlds; score is action efficiency
                against the BFS optimal path.
              </span>
            </li>
          </ol>
          <div className="ov-cta">
            <Link to="/challenge">
              <Button variant="primary">Beat the AI</Button>
            </Link>
            <Link to={firstGame ? `/play/${encodeURIComponent(firstGame)}` : '/play'}>
              <Button>Play &amp; Race Ghosts</Button>
            </Link>
            <Link to="/leaderboard">h1 Board</Link>
            <Link to="/leaderboard?view=h2">h2 Lab Board</Link>
            <Link to="/leaderboard?view=bench">Post-Training</Link>
            <Link to="/insights">Why Models Fail</Link>
            <Link to="/gallery">Gallery</Link>
            {!server.published && <Link to="/live">Live</Link>}
            <span className="muted ov-keys">
              <Kbd>←</Kbd>
              <Kbd>↑</Kbd>
              <Kbd>→</Kbd>
              <Kbd>↓</Kbd> move · <Kbd>R</Kbd> reset
            </span>
          </div>
        </div>
        <div className="ov-stage">{showcase ? <Showcase run={showcase} /> : <div className="ov-stage-empty" />}</div>
      </section>

      <section className="ov-stats">
        <div className="ov-stat-cell">
          <Stat label="games" value={games.data?.length ?? '—'} sub="in active collection" />
        </div>
        <div className="ov-stat-cell">
          <Stat label="rules" value={ruleCount || '—'} sub="mechanics in play" />
        </div>
        <div className="ov-stat-cell">
          <Stat label="runs" value={runs.data?.length ?? '—'} sub="recorded traces" />
        </div>
        <div className="ov-stat-cell">
          <Stat label="models" value={models || '—'} sub="evaluated" />
        </div>
        <div className="ov-stat-cell">
          <Stat label="human runs" value={humans || '—'} sub="first-attempt baseline" />
        </div>
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
                    <th className="num">score</th>
                    <th className="num">lvl solve</th>
                    <th className="num">game win</th>
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
                        <td className="num">{pct(r.level_solve_rate)}</td>
                        <td className="num">{pct(r.game_win_rate)}</td>
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

        <Panel label="latest runs" pad={false} actions={<Link to="/replay">all replays →</Link>}>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>player</th>
                  <th>kind</th>
                  <th>status</th>
                  <th className="num">levels</th>
                </tr>
              </thead>
              <tbody>
                {[...(runs.data ?? [])]
                  .sort((a, b) => (b.started_at ?? '').localeCompare(a.started_at ?? ''))
                  .slice(0, 6)
                  .map((r) => (
                    <tr key={r.run_id}>
                      <td>
                        <Link to={`/replay/${encodeURIComponent(r.run_id)}`}>{r.player?.name ?? r.player?.model_id}</Link>
                      </td>
                      <td className="secondary">{r.player?.kind}</td>
                      <td>
                        <Chip outcome={r.outcome ?? 'IN_PROGRESS'} />
                      </td>
                      <td className="num">
                        {r.levels_completed ?? 0}/{r.levels_total ?? '?'}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  )
}
