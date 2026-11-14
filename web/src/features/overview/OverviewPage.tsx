import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import type { RunMeta } from '@/lib/types'
import { useServerInfo } from '@/lib/server'
import type { LeaderboardDocument, LeaderboardRow } from '@/features/leaderboard/types'
import { Button, Chip, Kbd, Panel, Stat } from '@/design/primitives'
import './overview.css'

/** Pick a run worth showing on the front page: the best finished model run, else the optimal baseline. */
function pickShowcase(runs: RunMeta[]): RunMeta | undefined {
  const done = runs.filter((r) => r.outcome && r.outcome !== 'IN_PROGRESS' && (r.actions ?? 0) > 5)
  const score = (r: RunMeta) =>
    (r.outcome === 'WIN' ? 1e6 : 0) + (r.levels_completed ?? 0) * 1e4 - (r.outcome === 'ABORTED' ? 1e5 : 0) - (r.actions ?? 0)
  const models = done.filter((r) => r.player?.kind === 'model').sort((a, b) => score(b) - score(a))
  return models[0] ?? done.find((r) => /optimal/.test(r.player?.name ?? '')) ?? done[0]
}

function Showcase({ run }: { run: RunMeta }) {
  const steps = useQuery({ queryKey: ['steps', run.run_id], queryFn: () => api.getRunSteps(run.run_id), staleTime: Infinity })
  const [i, setI] = useState(0)
  const n = steps.data?.length ?? 0
  useEffect(() => {
    if (!n) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) return
    const t = setTimeout(() => setI((x) => (x + 1 >= n ? 0 : x + 1)), i + 1 >= n ? 2500 : 180)
    return () => clearTimeout(t)
  }, [i, n])
  const step = steps.data?.[i]
  return (
    <figure className="ov-showcase">
      <FrameCanvas frame={step?.frame} scale="fit" maxScale={8} label="A recorded run, playing back" />
      <figcaption className="mono muted">
        <Link to={`/replay/${encodeURIComponent(run.run_id)}`}>{run.player?.name ?? run.player?.model_id}</Link> on{' '}
        {run.game_id} · level {step?.truth?.level ?? '?'} · step {i + 1}/{n || '?'}
        {step?.hypothesis ? <span className="ov-hyp"> · “{step.hypothesis}”</span> : null}
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
  const rows: LeaderboardRow[] = useMemo(
    () => [...(lb.data?.rows ?? [])].sort((a, b) => b.score - a.score).slice(0, 8),
    [lb.data],
  )
  const firstGame = games.data?.[0]?.game_id

  return (
    <div className="ov">
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
                <b>Factory.</b> Seeded generator, BFS solvability proof, budget from the optimal solution, a rule must
                matter or the level is rejected.
              </span>
            </li>
            <li>
              <span className="mono ov-n">2</span>
              <span>
                <b>Pixels only.</b> Models and humans play the same frames through MCP, REST or the keyboard.
              </span>
            </li>
            <li>
              <span className="mono ov-n">3</span>
              <span>
                <b>Arena.</b> Frontier models, humans and baselines on held-out games; score is action efficiency against
                the optimal path.
              </span>
            </li>
          </ol>
          <div className="ov-cta">
            <Link to={firstGame ? `/play/${encodeURIComponent(firstGame)}` : '/play'}>
              <Button variant="primary">Play a game</Button>
            </Link>
            <Link to="/leaderboard">Leaderboard</Link>
            <Link to="/gallery">Gallery</Link>
            {!server.published && <Link to="/live">Live</Link>}
            <span className="muted ov-keys">
              <Kbd>←</Kbd>
              <Kbd>↑</Kbd>
              <Kbd>→</Kbd>
              <Kbd>↓</Kbd> to move, <Kbd>R</Kbd> to restart a level
            </span>
          </div>
        </div>
        <div className="ov-stage">{showcase ? <Showcase run={showcase} /> : <div className="ov-stage-empty" />}</div>
      </section>

      <section className="ov-stats">
        <Stat label="games" value={games.data?.length ?? '—'} sub="in this collection" />
        <Stat label="rules" value={ruleCount || '—'} sub="mechanics in play" />
        <Stat label="runs" value={runs.data?.length ?? '—'} sub="recorded traces" />
        <Stat label="models" value={models || '—'} sub="evaluated" />
        <Stat label="human runs" value={humans || '—'} sub="baseline" />
      </section>

      <div className="ov-bottom">
        <Panel label="leaderboard · top" pad={false} actions={<Link to="/leaderboard">full table</Link>}>
          {rows.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>player</th>
                    <th className="num">score</th>
                    <th className="num">levels solved</th>
                    <th className="num">games won</th>
                    <th className="num">$/game</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={`${r.player_id}-${r.effort ?? ''}-${r.collection}`}>
                      <td className="num muted">{i + 1}</td>
                      <td>
                        {r.display_name ?? r.model?.display_name ?? r.player_id}
                        {r.effort && <span className="muted"> · {r.effort}</span>}
                        {r.kind !== 'model' && <span className="muted"> · {r.kind}</span>}
                      </td>
                      <td className="num">{r.score.toFixed(2)}</td>
                      <td className="num">{pct(r.level_solve_rate)}</td>
                      <td className="num">{pct(r.game_win_rate)}</td>
                      <td className="num">{r.cost_per_game ? `$${r.cost_per_game.toFixed(3)}` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted ov-pad">{lb.isLoading ? 'Loading…' : 'Leaderboard not built yet.'}</p>
          )}
        </Panel>

        <Panel label="latest runs" pad={false} actions={<Link to="/replay">all runs</Link>}>
          <div className="table-wrap">
            <table className="table">
              <tbody>
                {[...(runs.data ?? [])]
                  .sort((a, b) => (b.started_at ?? '').localeCompare(a.started_at ?? ''))
                  .slice(0, 8)
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
