import { api, HttpError } from '@/lib/api'
import { API } from '@/lib/config'
import type { ActionName, Frame, LevelDescribe, Player, RunMeta, SessionStart, Step } from '@/lib/types'

export interface GhostStep {
  i: number
  action: ActionName
  events?: string[]
  state?: string
  hypothesis?: string | null
  belief?: string | null
  reasoning?: string | null
  frame?: Frame
}

export interface GhostSlice {
  run_id: string | null
  player: Player
  solved: boolean
  actions: number
  first_step?: number
  start_frame?: Frame | null
  steps: GhostStep[]
}

export interface GhostsResponse {
  game_id: string
  level: number
  optimal: GhostSlice | null
  ghosts: GhostSlice[]
}

export interface ExplanationEntry {
  run_id: string
  game_id?: string | null
  player_id?: string | null
  level: number
  step?: number | null
  rule?: string | null
  verdict: string
  explanation?: string | null
  evidence_quote?: string | null
  judge_model?: string | null
}

export interface ExplanationsDocument {
  generated_at: string
  judge_model?: string | null
  explanations: ExplanationEntry[]
}

// Static Vite asset bundle from rules/img/ so rule swatches work offline/mock and before server restarts
const bundledRuleImages = import.meta.glob('../../../../rules/img/*.{png,gif}', {
  eager: true,
  import: 'default',
}) as Record<string, string>

export function ruleImageUrl(rule: string, ext: 'png' | 'gif' = 'png'): string | null {
  if (!rule) return null
  const clean = rule.trim().toLowerCase()
  for (const [k, url] of Object.entries(bundledRuleImages)) {
    if (k.endsWith(`/${clean}.${ext}`)) return url
  }
  const anyApi = api as unknown as { ruleImageUrl?: (r: string, e?: string) => string | null }
  if (typeof anyApi.ruleImageUrl === 'function') {
    return anyApi.ruleImageUrl(clean, ext)
  }
  if (API.base) {
    return `${API.base}/rules/img/${encodeURIComponent(clean)}.${ext}`
  }
  return null
}

function sliceRunOnLevel(meta: RunMeta, steps: Step[], level: number): GhostSlice | null {
  if (!steps.length) return null
  let startFrame: Frame | null = null
  const sliced: GhostStep[] = []
  let solved = false

  for (let idx = 0; idx < steps.length; idx++) {
    const st = steps[idx]
    const lv = st.truth?.level ?? 1
    if (st.action === null) {
      if (lv === level && !startFrame) startFrame = st.frame
      continue
    }
    const prev = steps[idx - 1]
    const prevLv = prev?.truth?.level ?? lv
    if (prevLv === level) {
      if (!startFrame && prev?.frame) startFrame = prev.frame
      sliced.push({
        i: st.i,
        action: st.action,
        events: st.truth?.events ?? [],
        state: st.truth?.state,
        hypothesis: st.hypothesis ?? null,
        belief: st.belief ?? null,
        frame: st.frame,
      })
      if (lv > prevLv || st.truth?.state === 'WIN' || st.truth?.events?.includes('level_complete')) {
        solved = true
        break
      }
    } else if (lv === level && !startFrame) {
      startFrame = st.frame
    }
  }

  if (!sliced.length) return null
  return {
    run_id: meta.run_id,
    player: meta.player,
    solved,
    actions: sliced.length,
    first_step: sliced[0]?.i,
    start_frame: startFrame,
    steps: sliced,
  }
}

async function fallbackGhostsFromClient(gameId: string, level: number, limit: number): Promise<GhostsResponse> {
  const runs = await api.listRuns({ game_id: gameId })
  const finished = runs.filter(
    (r) =>
      r.outcome &&
      r.outcome !== 'IN_PROGRESS' &&
      !(r as Record<string, unknown>).start_level &&
      !(r as Record<string, unknown>).takeover_of,
  )

  // Pick best recorded run per model + optimal baseline
  const optMeta = finished.find(
    (r) => r.player?.kind === 'baseline' && /optimal/.test(r.player?.name ?? r.player?.model_id ?? ''),
  )
  const seenModels = new Set<string>()
  const modelMetas = finished
    .filter((r) => r.player?.kind === 'model')
    .sort((a, b) => (b.levels_completed ?? 0) * 1e5 - (b.actions ?? 0) - ((a.levels_completed ?? 0) * 1e5 - (a.actions ?? 0)))
    .filter((r) => {
      const id = `${r.player?.model_id ?? r.player?.name}::${r.player?.effort ?? ''}`
      if (seenModels.has(id)) return false
      seenModels.add(id)
      return true
    })
    .slice(0, limit)

  let optimal: GhostSlice | null = null
  if (optMeta) {
    try {
      const optSteps = await api.getRunSteps(optMeta.run_id)
      optimal = sliceRunOnLevel(optMeta, optSteps, level)
    } catch {
      optimal = null
    }
  }
  if (!optimal) {
    try {
      const desc = await api.getGame(gameId)
      const dlv: LevelDescribe | undefined = desc.levels?.find((l) => l.level === level)
      if (dlv?.optimal_path?.length) {
        optimal = {
          run_id: null,
          player: { kind: 'baseline', name: 'optimal' },
          solved: true,
          actions: dlv.optimal_path.length,
          start_frame: null,
          steps: dlv.optimal_path.map((a, idx) => ({
            i: idx + 1,
            action: a,
            events: idx === dlv.optimal_path!.length - 1 ? ['level_complete'] : [],
            state: 'NOT_FINISHED',
          })),
        }
      }
    } catch {
      /* ignore */
    }
  }

  const ghosts: GhostSlice[] = []
  await Promise.all(
    modelMetas.map(async (m) => {
      try {
        const st = await api.getRunSteps(m.run_id)
        const sl = sliceRunOnLevel(m, st, level)
        if (sl) ghosts.push(sl)
      } catch {
        /* ignore */
      }
    }),
  )
  ghosts.sort((a, b) => Number(b.solved) - Number(a.solved) || a.actions - b.actions)

  return { game_id: gameId, level, optimal, ghosts: ghosts.slice(0, limit) }
}

export async function fetchGhosts(gameId: string, level: number, limit = 3): Promise<GhostsResponse> {
  const anyApi = api as unknown as {
    getGhosts?: (gid: string, opts?: { level?: number; limit?: number }) => Promise<GhostsResponse>
  }
  if (typeof anyApi.getGhosts === 'function') {
    return anyApi.getGhosts(gameId, { level, limit })
  }
  if (API.base) {
    try {
      const url = `${API.base}/games/${encodeURIComponent(gameId)}/ghosts?level=${level}&limit=${limit}&kind=model&optimal=true&frames=true`
      const res = await fetch(url)
      if (res.ok) {
        return (await res.json()) as GhostsResponse
      }
      if (res.status !== 404 && res.status !== 405) {
        throw new HttpError(res.status, `ghosts ${res.status}`)
      }
    } catch {
      /* fall through to client slice fallback */
    }
  }
  return fallbackGhostsFromClient(gameId, level, limit)
}

export async function startSessionWithTakeover(opts: {
  gameId: string
  player: Player
  startLevel?: number
  takeoverOf?: { run_id: string; step: number }
}): Promise<SessionStart & { fallbackLevel1?: boolean }> {
  const { gameId, player, startLevel, takeoverOf } = opts
  if (!startLevel && !takeoverOf) {
    return api.createSession({ game_id: gameId, player })
  }
  if (API.base) {
    const res = await fetch(`${API.base}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game_id: gameId,
        player,
        ...(startLevel ? { start_level: startLevel } : {}),
        ...(takeoverOf ? { takeover_of: takeoverOf } : {}),
      }),
    })
    if (res.ok) {
      return (await res.json()) as SessionStart
    }
    // If live server has not restarted onto 4e693dc yet, fall back cleanly to Level 1
    if (res.status === 422 || res.status === 400) {
      const base = await api.createSession({ game_id: gameId, player: { ...player, name: 'test' } })
      return { ...base, fallbackLevel1: true }
    }
    const txt = await res.text()
    throw new HttpError(res.status, `${res.status} /sessions: ${txt.slice(0, 180)}`)
  }
  const base = await api.createSession({ game_id: gameId, player })
  return { ...base, fallbackLevel1: (startLevel ?? 1) > 1 }
}

export async function fetchExplanations(): Promise<ExplanationsDocument> {
  try {
    const doc = await api.derived<ExplanationsDocument>('explanations')
    if (doc && Array.isArray(doc.explanations)) return doc
  } catch {
    /* 404 when not yet built on older server */
  }
  return { generated_at: '', explanations: [] }
}
