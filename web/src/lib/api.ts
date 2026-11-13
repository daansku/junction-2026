import { API } from './config'
import { MockApi } from './mock'
import type {
  ActBody,
  ActResponse,
  GameDescribe,
  GameMeta,
  Player,
  RunMeta,
  RunsQuery,
  SessionStart,
  Step,
  Truth,
} from './types'

/** Every page talks to the backend only through this interface (PLAN.md §4.4). */
export interface Api {
  listGames(collection?: string): Promise<GameMeta[]>
  getGame(gameId: string): Promise<GameDescribe>
  thumbnailUrl(game: GameMeta): string | null
  createSession(body: { game_id: string; player: Player; run_key?: string }): Promise<SessionStart>
  act(sessionId: string, body: ActBody): Promise<ActResponse>
  truth(sessionId: string): Promise<Truth>
  endSession(sessionId: string, reason: string): Promise<void>
  listRuns(q?: RunsQuery): Promise<RunMeta[]>
  getRun(runId: string): Promise<RunMeta>
  getRunSteps(runId: string): Promise<Step[]>
  derived<T = unknown>(name: string): Promise<T>
  /** WebSocket URL for /live, or null when unsupported (mock). */
  liveUrl(): string | null
}

export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

class HttpApi implements Api {
  constructor(private base: string) {}

  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.base}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
    const text = await res.text()
    if (!res.ok) throw new HttpError(res.status, `${res.status} ${path}: ${text.slice(0, 200)}`)
    return parseJsonOrLines(text) as T
  }

  private post<T>(path: string, body: unknown) {
    return this.req<T>(path, { method: 'POST', body: JSON.stringify(body) })
  }

  async listGames(collection?: string) {
    const q = collection ? `?collection=${encodeURIComponent(collection)}` : ''
    return unwrapList<GameMeta>(await this.req(`/games${q}`), 'games')
  }
  getGame(id: string) {
    return this.req<GameDescribe>(`/games/${encodeURIComponent(id)}`)
  }
  thumbnailUrl(game: GameMeta) {
    const t = game.thumbnail_url
    if (!t) return null
    if (/^https?:/.test(t)) return t
    // Server may return "/api/…" or "/games/…"; resolve against API origin.
    const origin = new URL(this.base, window.location.href)
    return t.startsWith('/api') ? new URL(t, origin).toString() : `${this.base}${t.startsWith('/') ? '' : '/'}${t}`
  }
  createSession(body: { game_id: string; player: Player; run_key?: string }) {
    return this.post<SessionStart>('/sessions', body)
  }
  act(id: string, body: ActBody) {
    return this.post<ActResponse>(`/sessions/${id}/act`, body)
  }
  truth(id: string) {
    return this.req<Truth>(`/sessions/${id}/truth`)
  }
  async endSession(id: string, reason: string) {
    await this.post(`/sessions/${id}/end`, { reason })
  }
  async listRuns(q: RunsQuery = {}) {
    const p = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v && p.set(k, v))
    const qs = p.toString()
    return unwrapList<RunMeta>(await this.req(`/runs${qs ? `?${qs}` : ''}`), 'runs')
  }
  getRun(id: string) {
    return this.req<RunMeta>(`/runs/${id}`)
  }
  async getRunSteps(id: string) {
    return unwrapList<Step>(await this.req(`/runs/${id}/steps`), 'steps')
  }
  derived<T>(name: string) {
    return this.req<T>(`/derived/${name}.json`)
  }
  liveUrl() {
    const u = new URL(`${this.base}/live`, window.location.href)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    return u.toString()
  }
}

/** JSON, or JSON Lines (steps.jsonl served raw). */
export function parseJsonOrLines(text: string): unknown {
  const t = text.trim()
  if (!t) return null
  try {
    return JSON.parse(t)
  } catch {
    return t
      .split('\n')
      .filter((l) => l.trim())
      .map((l) => JSON.parse(l))
  }
}

function unwrapList<T>(v: unknown, key: string): T[] {
  if (Array.isArray(v)) return v as T[]
  if (v && typeof v === 'object') {
    const o = v as Record<string, unknown>
    for (const k of [key, 'items', 'data', 'results']) if (Array.isArray(o[k])) return o[k] as T[]
  }
  return []
}

export const api: Api = API.base ? new HttpApi(API.base) : new MockApi()
