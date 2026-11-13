// Owned by A5 (PLAN.md §3.2). Stub from A4's shell — replace freely.
// Data: api.derived('insights'), api.derived('rules'). Rules: web/DESIGN.md.
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Empty, ErrorState, Loading, PageHeader, Panel } from '@/design/primitives'

export function InsightsPage() {
  const q = useQuery({ queryKey: ['derived', 'insights'], queryFn: () => api.derived('insights') })
  return (
    <>
      <PageHeader title="Insights" sub="Owned by A5. Stub until features/insights lands." />
      <Panel label="insights.json">
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
