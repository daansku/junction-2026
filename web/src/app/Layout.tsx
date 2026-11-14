import { NavLink, Outlet } from 'react-router-dom'
import { API, setApiMode, SHARED_URL } from '@/lib/config'
import { PALETTE_SOURCE } from '@/lib/palette'
import { useServerInfo } from '@/lib/server'
import { Wordmark } from './Wordmark'
import { ThemeToggle } from './ThemeToggle'
import './layout.css'

const NAV = [
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
        <div className="topbar-right">
          <label className="api-pick" title={API.base ?? 'in-browser mock backend'}>
            <span className="kicker">data</span>
            <select value={API.mode === 'same-origin' || API.mode === 'custom' ? 'other' : API.mode} onChange={(e) => setApiMode(e.target.value)}>
              <option value="mock">mock</option>
              <option value="local">localhost</option>
              <option value="shared" disabled={!SHARED_URL}>shared{SHARED_URL ? '' : ' (no URL yet)'}</option>
              {(API.mode === 'same-origin' || API.mode === 'custom') && <option value="other">{API.label}</option>}
            </select>
          </label>
          <ThemeToggle />
        </div>
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
