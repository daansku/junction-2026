import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { MockApi } from '@/lib/mock'
import type { GameMeta } from '@/lib/types'
import { Empty, ErrorState, Loading, PageHeader } from '@/design/primitives'
import './gallery.css'

function Thumb({ game }: { game: GameMeta }) {
  const url = api.thumbnailUrl(game)
  if (url) return <img className="thumb" src={url} alt="" width={192} height={192} loading="lazy" />
  const frame = api instanceof MockApi ? api.previewFrame(game.game_id) : null
  return frame ? <FrameCanvas frame={frame} scale={3} /> : <div className="thumb thumb-empty" />
}

export function GalleryPage() {
  const games = useQuery({ queryKey: ['games'], queryFn: () => api.listGames() })
  return (
    <>
      <PageHeader title="Gallery" sub="Every game is seeded, multi-level and proven solvable." />
      {games.isLoading ? (
        <Loading what="Loading games" />
      ) : games.error ? (
        <ErrorState error={games.error} retry={() => games.refetch()} />
      ) : !games.data?.length ? (
        <Empty>No games in this collection.</Empty>
      ) : (
        <div className="gallery-grid">
          {games.data.map((g) => (
            <article key={g.game_id} className="game-card">
              <Thumb game={g} />
              <div className="game-card-meta">
                <span className="mono game-id">{g.game_id}</span>
                <span className="muted mono">
                  d{g.difficulty ?? g.spec?.difficulty ?? '?'} · {g.levels_total ?? g.spec?.n_levels ?? g.n_levels ?? '?'} levels
                  {g.optimal_moves_total ? ` · opt ${g.optimal_moves_total}` : ''}
                </span>
                <span className="game-card-links">
                  <Link to={`/play/${encodeURIComponent(g.game_id)}`}>Play</Link>
                  <Link to={`/replay?game_id=${encodeURIComponent(g.game_id)}`}>Runs</Link>
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  )
}
