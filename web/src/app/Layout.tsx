import { NavLink, Outlet } from 'react-router-dom'
import { API } from '@/lib/config'
import { PALETTE_SOURCE } from '@/lib/palette'
import { useServerInfo } from '@/lib/server'
import { Wordmark } from './Wordmark'
import './layout.css'

const NAV = [
  { to: '/challenge', label: 'Challenge' },
  { to: '/play', label: 'Play' },
  { to: '/gallery', label: 'Gallery' },
  { to: '/replay', label: 'Replays' },
  { to: '/live', label: 'Live' },
  { to: '/compare', label: 'Compare' },
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/insights', label: 'Insights' },
]

export function Layout() {
  const server = useServerInfo()
  const nav = NAV.filter((n) => !(server.published && n.to === '/live'))
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="Home">
          <Wordmark />
        </NavLink>
        <nav className="nav" aria-label="Main">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      {API.mode === 'mock' && (
        <div className="mock-banner mono">
          MOCK DATA — fixtures + in-browser fake engine. Not results.
          {PALETTE_SOURCE === 'fallback' && ' Palette: built-in fallback (contracts/palette.json missing).'}
        </div>
      )}
      {server.published && (
        <div className="published-banner mono">
          Published snapshot: results are frozen. You can play every game; your plays are not added to the results.
        </div>
      )}
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
