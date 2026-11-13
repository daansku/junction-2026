// Owned by A5 (PLAN.md §3.2). Stub from A4's shell — replace freely.
// Data: api.derived('leaderboard'). Charts: PlotFigure from '@/lib/PlotFigure'. Rules: web/DESIGN.md.
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Empty, ErrorState, Loading, PageHeader, Panel } from '@/design/primitives'

export function LeaderboardPage() {
  const q = useQuery({ queryKey: ['derived', 'leaderboard'], queryFn: () => api.derived('leaderboard') })
  return (
    <>
      <PageHeader title="Leaderboard" sub="Owned by A5. Stub until features/leaderboard lands." />
      <Panel label="leaderboard.json">
        {q.isLoading ? (
          <Loading />
        ) : q.error ? (
          <ErrorState error={q.error} retry={() => q.refetch()} />
        ) : q.data ? (
          <pre className="mono" style={{ maxHeight: 480, overflow: 'auto', margin: 0 }}>
            {JSON.stringify(q.data, null, 2).slice(0, 4000)}
          </pre>
        ) : (
          <Empty>No data.</Empty>
        )}
      </Panel>
    </>
  )
}
