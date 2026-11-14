// Data for the /challenge demo: precomputed per-level stats (web/scripts/challenge_stats.py) and the
// visitor board. The board uses A2's endpoints when the server has them (PLAN.md A2-22:
// POST /challenge/score, GET /challenge/board) and otherwise falls back to this browser only,
// labelled as such. Visitor plays never go to the research board: sessions carry player.mode
// "challenge" (coordination/requests/A4-to-A5-challenge-runs-filter.md).
import { API } from '@/lib/config'

/**
 * Challenge set (human decision Sat ~19:30, "for now"): eval-v1 games a person has beaten, with the most models
 * recorded on them; first 3 levels each. A: s900000 (d1, 8+ models finished). B: s900002 (d3, models still running).
 * The eval-v2 set (s910000 / s910019 / s910021, games people finished) is kept below for when its model runs land.
 * `?game=<id>` opens any game.
 */
export const CHALLENGE_GAMES: Array<{ id: string; label: string }> = [
  { id: 'gridworld-s900000-d1-l6-33a57ce4', label: 'A' },
  { id: 'gridworld-s900002-d3-l6-f09d6348', label: 'B' },
]
export const EVAL_V2_GAMES = ['gridworld-s910000-d4-l8-f71ee29e', 'gridworld-s910019-d4-l8-50cff9f4', 'gridworld-s910021-d4-l8-404033da']
export const DEFAULT_GAME = CHALLENGE_GAMES[0].id
export const DEFAULT_LEVELS = 3
export const NAME_MAX = 20

export interface StatsLevel {
  level: number
  solved: boolean
  actions: number
}

export interface StatsPlayer {
  id: string
  kind: 'human' | 'model'
  name: string
  model_id: string | null
  attempts: number
  mean_score: number
  best_score: number
  cleared_all_rate: number
  per_level_solve_rate: number[]
  runs: Array<{ run_id: string; levels: StatsLevel[]; score: number; cleared: number }>
}

export interface ChallengeStats {
  game_id: string
  levels: number
  start_level?: number
  optimal_moves: number[]
  generated_at: string
  score_rule: string
  players: StatsPlayer[]
}

export async function loadStats(gameId: string, from: number): Promise<ChallengeStats | null> {
  const file = from === 1 ? `${gameId}.json` : `${gameId}-from${from}.json`
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}challenge/${file}`)
    if (!res.ok) return null
    const doc = (await res.json()) as ChallengeStats
    return Array.isArray(doc.players) ? doc : null
  } catch {
    return null
  }
}

/** Per level: min(1, optimal / actions) when solved, else 0. Mean x 100. Same rule as the arena score. */
export function challengeScore(levels: Array<{ solved: boolean; actions: number }>, optimal: number[]): number {
  if (!optimal.length) return 0
  const s = optimal.reduce((acc, opt, i) => {
    const lv = levels[i]
    return acc + (lv?.solved && lv.actions > 0 ? Math.min(1, opt / lv.actions) : 0)
  }, 0)
  return Math.round((1000 * s) / optimal.length) / 10
}

export function cleanName(raw: string): string {
  return raw
    .replace(/[^\p{L}\p{N} _.-]/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, NAME_MAX)
}

/** One board row. Server rows (A2-22) are computed from the recorded run, not sent by the client. */
export interface BoardEntry {
  name: string
  levels_completed: number
  actions: number
  beat_ai: boolean
  at: string
  run_id?: string | null
  /** local fallback only: our challenge score (server rows rank by levels, then actions) */
  score?: number
}

export interface Board {
  source: 'server' | 'local'
  entries: BoardEntry[]
}

const localKey = (gameId: string) => `challengeBoard:${gameId}`

function readLocal(gameId: string): BoardEntry[] {
  try {
    const v = JSON.parse(localStorage.getItem(localKey(gameId)) ?? '[]')
    return Array.isArray(v) ? (v as BoardEntry[]).filter((e) => typeof e.levels_completed === 'number') : []
  } catch {
    return []
  }
}

/** Same order as the server board: more levels, then fewer actions, then earlier. */
function sortBoard(entries: BoardEntry[]): BoardEntry[] {
  return [...entries].sort(
    (a, b) => b.levels_completed - a.levels_completed || a.actions - b.actions || a.at.localeCompare(b.at),
  )
}

export async function fetchBoard(gameId: string): Promise<Board> {
  if (API.base) {
    try {
      const res = await fetch(`${API.base}/challenge/board?game_id=${encodeURIComponent(gameId)}&limit=10`)
      if (res.ok) {
        const doc = (await res.json()) as { rows?: BoardEntry[] }
        return { source: 'server', entries: (doc.rows ?? []).slice(0, 10) }
      }
    } catch {
      /* server without the board yet: local fallback */
    }
  }
  return { source: 'local', entries: sortBoard(readLocal(gameId)).slice(0, 10) }
}

/**
 * Server board: POST {run_id, name, beat_ai}; the server reads levels/actions from the run, which must be ended
 * first (409 while IN_PROGRESS). Falls back to this browser when the endpoint is missing or refuses.
 */
export async function submitScore(gameId: string, e: BoardEntry): Promise<'server' | 'local'> {
  if (API.base && e.run_id) {
    try {
      const res = await fetch(`${API.base}/challenge/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: e.run_id, name: e.name, beat_ai: e.beat_ai }),
      })
      if (res.ok) return 'server'
    } catch {
      /* fall through */
    }
  }
  try {
    const all = sortBoard([...readLocal(gameId), e]).slice(0, 50)
    localStorage.setItem(localKey(gameId), JSON.stringify(all))
  } catch {
    /* storage blocked: the score is still on screen */
  }
  return 'local'
}

export function clearLocalBoard(gameId: string) {
  try {
    localStorage.removeItem(localKey(gameId))
  } catch {
    /* ignore */
  }
}
