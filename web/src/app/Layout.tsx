import { Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { API, setApiMode, SHARED_URL } from '@/lib/config'
import { useDevMode } from '@/lib/devMode'
import { PALETTE_SOURCE } from '@/lib/palette'
import { useServerInfo } from '@/lib/server'
import { Wordmark } from './Wordmark'
import { ThemeToggle } from './ThemeToggle'
import './layout.css'

interface NavItem {
  to: string
  label: string
  devOnly?: boolean
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Overview', devOnly: true, end: true },
  { to: '/challenge', label: 'Challenge' },
  { to: '/play', label: 'Play' },
  { to: '/insights', label: 'Insights' },
  { to: '/leaderboard', label: 'Leaderboard', devOnly: true },
  { to: '/gallery', label: 'Gallery', devOnly: true },
  { to: '/replay', label: 'Replays', devOnly: true },
  { to: '/compare', label: 'Compare', devOnly: true },
  { to: '/live', label: 'Live', devOnly: true },
]

function isAllowedInPublicMode(pathname: string): boolean {
  if (pathname === '/challenge' || pathname.startsWith('/challenge/')) return true
  if (pathname === '/play' || pathname.startsWith('/play/')) return true
  if (pathname === '/insights' || pathname.startsWith('/insights/')) return true
  // Allow deep-linked single-run X-Ray replays opened from Insights or Challenge end screen
  if (pathname.startsWith('/replay/') && pathname.length > '/replay/'.length) return true
  return false
}

export function Layout() {
  const server = useServerInfo()
  const [devMode, setDevMode] = useDevMode()
  const location = useLocation()

  const nav = NAV.filter((n) => {
    if (!devMode && n.devOnly) return false
    if (server.published && n.to === '/live') return false
    return true
  })

  const redirectPublic = !devMode && !isAllowedInPublicMode(location.pathname)

  return (
    <div className="app">
      <header className="topbar">
        <NavLink to={devMode ? '/' : '/challenge'} className="brand" aria-label="Home">
          <Wordmark />
        </NavLink>
        <nav className="nav" aria-label="Main">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="topbar-right">
          <button
            type="button"
            role="switch"
            aria-checked={devMode}
            className={`dev-switch ${devMode ? 'on' : ''}`}
            onClick={() => setDevMode(!devMode)}
            title="Toggle developer mode to show all pages"
          >
            <span className="dev-switch-track" aria-hidden="true">
              <span className="dev-switch-thumb" />
            </span>
            <span className="dev-switch-label mono">Developer mode</span>
          </button>
          {devMode && (
            <label className="api-pick" title={API.base ?? 'in-browser mock backend'}>
              <span className="kicker">data</span>
              <select
                value={API.mode === 'same-origin' || API.mode === 'custom' ? 'other' : API.mode}
                onChange={(e) => setApiMode(e.target.value)}
              >
                <option value="mock">mock</option>
                <option value="local">localhost</option>
                <option value="shared" disabled={!SHARED_URL}>
                  shared{SHARED_URL ? '' : ' (no URL yet)'}
                </option>
                {(API.mode === 'same-origin' || API.mode === 'custom') && <option value="other">{API.label}</option>}
              </select>
            </label>
          )}
          <ThemeToggle />
        </div>
      </header>
      {devMode && API.mode === 'mock' && (
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
        {redirectPublic ? <Navigate to="/challenge" replace /> : <Outlet />}
      </main>
    </div>
  )
}
