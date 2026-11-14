import { useQuery } from '@tanstack/react-query'
import { api } from './api'

function forcedPublished(): boolean {
  try {
    return new URLSearchParams(window.location.search).get('published') === '1'
  } catch {
    return false
  }
}

/**
 * Server capabilities. In published mode (A2-11) the server serves a frozen snapshot:
 * visitor plays are not listed under /runs, so their replays and the live wall are hidden.
 */
export function useServerInfo() {
  const q = useQuery({ queryKey: ['health'], queryFn: () => api.health(), staleTime: 60_000, retry: 1 })
  return { ...q.data, published: forcedPublished() || !!q.data?.published_mode, loaded: q.isFetched }
}
