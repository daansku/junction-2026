import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { Layout } from './Layout'
import { PlayPage } from '@/features/play/PlayPage'
import { GalleryPage } from '@/features/gallery/GalleryPage'
import { ReplayPage, ReplayIndexPage } from '@/features/replay/ReplayPage'
import { OverviewPage } from '@/features/overview/OverviewPage'
import { LiveWall } from '@/features/replay/LiveWall'
import { ComparePage } from '@/features/compare/ComparePage'
import { LeaderboardPage } from '@/features/leaderboard/LeaderboardPage'
import { InsightsPage } from '@/features/insights/InsightsPage'
import { ChallengePage } from '@/features/challenge/ChallengePage'
import { NotFound } from './NotFound'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
})

const router = createBrowserRouter([
  // Booth kiosk: the challenge without the top bar.
  { path: '/kiosk', element: <ChallengePage kiosk /> },
  {
    element: <Layout />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'challenge', element: <ChallengePage /> },
      { path: 'play', element: <PlayPage /> },
      { path: 'play/:gameId', element: <PlayPage /> },
      { path: 'gallery', element: <GalleryPage /> },
      { path: 'gallery/:gameId', element: <GalleryPage /> },
      { path: 'replay', element: <ReplayIndexPage /> },
      { path: 'replay/:run', element: <ReplayPage /> },
      { path: 'live', element: <LiveWall /> },
      { path: 'compare', element: <ComparePage /> },
      { path: 'leaderboard', element: <LeaderboardPage /> },
      { path: 'insights', element: <InsightsPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
