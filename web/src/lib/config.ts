// Where the web app gets data from. VITE_API is an optional build-time override.
// Otherwise development uses the shared server when available and production uses
// the server serving the app. Mock mode is only an explicit fallback.

const apiUrlFiles = import.meta.glob('../../../API_URL*', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

export const SHARED_URL: string | null = (() => {
  const raw = Object.values(apiUrlFiles)[0]
  const line = raw
    ?.split('\n')
    .map((l) => l.trim())
    .find((l) => /^https?:\/\//.test(l))
  return line ?? null
})()

function withApiSuffix(url: string): string {
  const u = url.replace(/\/+$/, '')
  return /\/api$/.test(u) ? u : `${u}/api`
}

export type ApiMode = 'mock' | 'local' | 'shared' | 'same-origin' | 'custom'

export interface ApiConfig {
  mode: ApiMode
  base: string | null // null for mock
  label: string
}

/**
 * Accept only values the resolver understands. Anything else is ignored, so a mangled build
 * variable can't break the site: Git Bash on Windows rewrites VITE_API=/api to
 * "C:/Program Files/Git/api", which shipped once and left new visitors with no server.
 */
function validPick(v: string | null | undefined): string | null {
  if (!v) return null
  const s = v.trim()
  if (s === 'mock' || s === 'local' || s === 'shared') return s
  if (s.startsWith('/') && !s.startsWith('//')) return s
  if (/^https?:\/\/[^/\s]+/.test(s)) return s
  console.warn(`[api] ignoring invalid API setting ${JSON.stringify(v)}`)
  return null
}

export function resolveApi(): ApiConfig {
  const pick =
    validPick(import.meta.env.VITE_API as string | undefined) ??
    (import.meta.env.DEV && SHARED_URL ? 'shared' : '/api')
  if (pick === 'mock') return { mode: 'mock', base: null, label: 'mock' }
  if (pick === 'local') return { mode: 'local', base: 'http://localhost:8000/api', label: 'localhost' }
  if (pick === 'shared') {
    if (!SHARED_URL) return { mode: 'mock', base: null, label: 'mock (no API_URL yet)' }
    return { mode: 'shared', base: withApiSuffix(SHARED_URL), label: 'shared' }
  }
  if (pick.startsWith('/')) return { mode: 'same-origin', base: pick.replace(/\/+$/, ''), label: 'server' }
  return { mode: 'custom', base: withApiSuffix(pick), label: new URL(pick).host }
}

export const API = resolveApi()
