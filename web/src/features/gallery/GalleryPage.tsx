import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { MockApi } from '@/lib/mock'
import type { GameMeta } from '@/lib/types'
import { Empty, ErrorState, Loading, PageHeader } from '@/design/primitives'
import { GameDetail } from './GameDetail'
import './gallery.css'

function Thumb({ game }: { game: GameMeta }) {
  const url = api.thumbnailUrl(game)
  if (url && !(api instanceof MockApi))
    return <img className="thumb" src={url} alt="" width={192} height={192} loading="lazy" />
  const frame = api instanceof MockApi ? api.previewFrame(game.game_id) : null
  return frame ? <FrameCanvas frame={frame} scale={3} /> : <div className="thumb thumb-empty" />
}

const diffOf = (g: GameMeta) => g.difficulty ?? g.spec?.difficulty
const levelsOf = (g: GameMeta) => g.levels_total ?? g.spec?.n_levels ?? g.n_levels

export function GalleryPage() {
  const { gameId } = useParams()
  if (gameId) return <GameDetail gameId={gameId} />
  return <GalleryList />
}

function GalleryList() {
  const [params, setParams] = useSearchParams()
  const collections = useQuery({ queryKey: ['collections'], queryFn: () => api.listCollections() })
  const collection = params.get('collection') ?? (collections.data?.includes('dev') ? 'dev' : collections.data?.[0])
  const rule = params.get('rule') ?? ''
  const diff = params.get('difficulty') ?? ''
  const games = useQuery({
    queryKey: ['games', collection],
    queryFn: () => api.listGames(collection),
    enabled: collections.isFetched,
  })

  const allRules = useMemo(
    () => [...new Set((games.data ?? []).flatMap((g) => g.rules ?? []))].sort(),
    [games.data],
  )
  const allDiffs = useMemo(
    () => [...new Set((games.data ?? []).map(diffOf).filter((d) => d != null))].sort(),
    [games.data],
  )
  const shown = (games.data ?? []).filter(
    (g) => (!rule || g.rules?.includes(rule)) && (!diff || String(diffOf(g)) === diff),
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
        title="Gallery"
        sub="Every game is seeded, multi-level and proven solvable by BFS. One new rule per level."
        actions={
          <>
            {(collections.data?.length ?? 0) > 1 && (
              <label className="field">
                <span className="kicker">set</span>
                <select value={collection ?? ''} onChange={(e) => setParam('collection', e.target.value)}>
                  {collections.data!.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="field">
              <span className="kicker">rule</span>
              <select value={rule} onChange={(e) => setParam('rule', e.target.value)}>
                <option value="">any</option>
                {allRules.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="kicker">difficulty</span>
              <select value={diff} onChange={(e) => setParam('difficulty', e.target.value)}>
                <option value="">any</option>
                {allDiffs.map((d) => (
                  <option key={d} value={String(d)}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <span className="mono muted">
              {shown.length}/{games.data?.length ?? 0}
            </span>
          </>
        }
      />
      {games.isLoading || collections.isLoading ? (
        <Loading what="Loading games" />
      ) : games.error ? (
        <ErrorState error={games.error} retry={() => games.refetch()} />
      ) : !shown.length ? (
        <Empty>No games match these filters.</Empty>
      ) : (
        <div className="gallery-grid">
          {shown.map((g) => {
            const href = `/gallery/${encodeURIComponent(g.game_id)}`
            return (
              <article key={g.game_id} className="game-card">
                <Link to={href} className="thumb-link" aria-label={`Open ${g.game_id}`}>
                  <Thumb game={g} />
                </Link>
                <div className="game-card-meta">
                  <Link to={href} className="mono game-id">
                    {g.game_id}
                  </Link>
                  <span className="muted mono">
                    d{diffOf(g) ?? '?'} · {levelsOf(g) ?? '?'} lv
                    {g.optimal_moves_total ? ` · opt ${g.optimal_moves_total}` : ''}
                  </span>
                  {!!g.rules?.length && <span className="mono game-rules">{g.rules.join(' · ')}</span>}
                  <span className="game-card-links">
                    <Link to={`/play/${encodeURIComponent(g.game_id)}`}>Play</Link>
                    <Link to={`/replay?game_id=${encodeURIComponent(g.game_id)}`}>Runs</Link>
                  </span>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </>
  )
}
