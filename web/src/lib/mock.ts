// Mock backend: reads committed fixtures from data/fixtures/ (A2, A5) and
// fills gaps with a tiny in-browser fake engine (walls + goal + budget), so
// every page works with no server. Never used for results.
import type { Api } from './api'
import { encodeFrame, FRAME_SIZE } from './frame'
import type {
  ActBody,
  ActionName,
  ActResponse,
  Frame,
  GameDescribe,
  GameMeta,
  LevelDescribe,
  Player,
  RunMeta,
  RunsQuery,
  SessionStart,
  Step,
  Truth,
} from './types'

// ---------- fixtures ----------

const fixtureLoaders = import.meta.glob('../../../data/fixtures/**/*.{json,jsonl}', {
  query: '?raw',
  import: 'default',
}) as Record<string, () => Promise<string>>

function relPath(k: string) {
  return k.replace(/^.*data\/fixtures\//, '')
}

function parseAny(text: string): unknown {
  const t = text.trim()
  try {
    return JSON.parse(t)
  } catch {
    return t
      .split('\n')
      .filter(Boolean)
      .map((l) => JSON.parse(l))
  }
}

interface Fixtures {
  games: GameMeta[]
  describes: Record<string, GameDescribe>
  runs: Record<string, { meta: RunMeta; stepsPath?: string }>
  derived: Record<string, string>
  frames: Record<string, Frame>
}

let fixturesPromise: Promise<Fixtures> | null = null

function loadFixtures(): Promise<Fixtures> {
  if (fixturesPromise) return fixturesPromise
  fixturesPromise = (async () => {
    const fx: Fixtures = { games: [], describes: {}, runs: {}, derived: {}, frames: {} }
    const entries = Object.entries(fixtureLoaders)
    for (const [key, load] of entries) {
      const rel = relPath(key)
      if (rel.startsWith('derived/')) {
        fx.derived[rel.slice('derived/'.length).replace(/\.json$/, '')] = key
        continue
      }
      if (rel.endsWith('meta.json')) {
        try {
          const meta = parseAny(await load()) as RunMeta
          if (meta?.run_id) {
            const dir = key.slice(0, key.length - 'meta.json'.length)
            const stepsKey = `${dir}steps.jsonl`
            fx.runs[meta.run_id] = { meta, stepsPath: fixtureLoaders[stepsKey] ? stepsKey : undefined }
          }
        } catch {
          /* ignore malformed fixture */
        }
        continue
      }
      if (rel.endsWith('.jsonl')) continue
      try {
        const v = parseAny(await load())
        const list = Array.isArray(v)
          ? v
          : v && typeof v === 'object'
            ? ((v as Record<string, unknown>).games as unknown[] | undefined)
            : undefined
        const isGame = (g: unknown) => !!g && typeof g === 'object' && 'game_id' in g && !('run_id' in g)
        if (Array.isArray(list) && list.length && list.every(isGame)) {
          for (const g of list as GameDescribe[]) {
            fx.games.push(g)
            if (Array.isArray(g.levels)) fx.describes[g.game_id] = g
          }
        } else if (v && typeof v === 'object' && 'game_id' in v && 'levels' in v) {
          const g = v as GameDescribe
          fx.describes[g.game_id] = g
        } else if (Array.isArray(v) && rel.startsWith('frames/') && v.length === FRAME_SIZE) {
          fx.frames[rel.slice('frames/'.length).replace(/\.json$/, '')] = v as Frame
        }
      } catch {
        /* not a game file */
      }
    }
    // dedupe games by id (games.json + games/*.json both list them)
    const seen = new Set<string>()
    fx.games = fx.games.filter((g) => !seen.has(g.game_id) && !!seen.add(g.game_id))
    for (const id of Object.keys(fx.describes)) if (!seen.has(id)) fx.games.push(fx.describes[id])
    return fx
  })()
  return fixturesPromise
}

// ---------- fake engine ----------

const GRID = 10
const CELL = 6
const OX = 2
const OY = 4
// Indices follow contracts/palette.json: 0 black, 1 blue, 2 red, 3 green, 4 yellow, 5 grey, 10 white, 11 dark_grey
const C = { bg: 0, floor: 0, wall: 5, player: 1, goal: 3, budget: 4, used: 11, pipDone: 3, pipNow: 10, pipTodo: 11, win: 3, lose: 2 }

function rng(seed: number) {
  let s = seed >>> 0 || 1
  return () => {
    s ^= s << 13
    s ^= s >>> 17
    s ^= s << 5
    return (s >>> 0) / 4294967296
  }
}

interface MockLevel {
  walls: boolean[]
  start: number
  goal: number
  optimal: ActionName[]
  budget: number
}

const DIRS: Array<[ActionName, number, number]> = [
  ['ACTION1', 0, -1],
  ['ACTION2', 0, 1],
  ['ACTION3', -1, 0],
  ['ACTION4', 1, 0],
]

function bfs(walls: boolean[], start: number, goal: number): ActionName[] | null {
  const prev = new Map<number, [number, ActionName]>()
  const q = [start]
  const seen = new Set([start])
  while (q.length) {
    const p = q.shift()!
    if (p === goal) {
      const path: ActionName[] = []
      let c = goal
      while (c !== start) {
        const [pp, a] = prev.get(c)!
        path.unshift(a)
        c = pp
      }
      return path
    }
    const x = p % GRID
    const y = Math.floor(p / GRID)
    for (const [a, dx, dy] of DIRS) {
      const nx = x + dx
      const ny = y + dy
      const n = ny * GRID + nx
      if (nx < 0 || ny < 0 || nx >= GRID || ny >= GRID || walls[n] || seen.has(n)) continue
      seen.add(n)
      prev.set(n, [p, a])
      q.push(n)
    }
  }
  return null
}

function makeLevel(seed: number, level: number): MockLevel {
  for (let attempt = 0; ; attempt++) {
    const r = rng(seed * 7919 + level * 104729 + attempt * 31)
    const walls = Array.from({ length: GRID * GRID }, (_, i) => {
      const x = i % GRID
      const y = Math.floor(i / GRID)
      if (x === 0 || y === 0 || x === GRID - 1 || y === GRID - 1) return true
      return r() < 0.18 + level * 0.04
    })
    const free = walls.map((w, i) => (w ? -1 : i)).filter((i) => i >= 0)
    const start = free[Math.floor(r() * free.length)]
    const goal = free[Math.floor(r() * free.length)]
    if (start === goal) continue
    const path = bfs(walls, start, goal)
    if (!path || path.length < 5 + level * 2) continue
    return { walls, start, goal, optimal: path, budget: Math.ceil(path.length * 2) + 4 }
  }
}

interface MockGame {
  meta: GameDescribe
  levels: MockLevel[]
}

const MOCK_GAMES: MockGame[] = [
  { seed: 1234, d: 1, n: 3 },
  { seed: 4242, d: 2, n: 4 },
  { seed: 9001, d: 3, n: 5 },
].map(({ seed, d, n }) => {
  const levels = Array.from({ length: n }, (_, i) => makeLevel(seed, i))
  const game_id = `mock-s${seed}-d${d}-l${n}`
  const lv: LevelDescribe[] = levels.map((l, i) => ({
    level: i + 1,
    rules: ['walls', 'goal'],
    new_rule: i === 0 ? 'goal' : null,
    move_budget: l.budget,
    optimal_moves: l.optimal.length,
    optimal_path: l.optimal,
  }))
  return {
    levels,
    meta: {
      game_id,
      collection: 'mock',
      family: 'gridworld',
      seed,
      difficulty: d,
      n_levels: n,
      levels_total: n,
      rules: ['walls', 'goal'],
      levels: lv,
      engine_version: 'mock-0',
    },
  }
})

interface SimState {
  game: MockGame
  level: number
  pos: number
  moves: number
  resets: number
  state: 'NOT_FINISHED' | 'WIN' | 'GAME_OVER'
  events: string[]
}

function render(s: SimState): Frame {
  const cells = new Uint8Array(FRAME_SIZE * FRAME_SIZE).fill(C.bg)
  const set = (x: number, y: number, c: number) => {
    if (x >= 0 && y >= 0 && x < FRAME_SIZE && y < FRAME_SIZE) cells[y * FRAME_SIZE + x] = c
  }
  const L = s.game.levels[Math.min(s.level, s.game.levels.length - 1)]
  // HUD: budget bar rows 0–1, x 0..47
  const barW = 48
  const left = Math.max(0, Math.round(barW * (1 - s.moves / L.budget)))
  for (let x = 0; x < barW; x++) for (let y = 0; y < 2; y++) set(x, y, x < left ? C.budget : C.used)
  // level pips at the right
  s.game.levels.forEach((_, i) => {
    const c = i < s.level ? C.pipDone : i === s.level ? C.pipNow : C.pipTodo
    set(52 + i * 3, 0, c)
    set(53 + i * 3, 0, c)
    set(52 + i * 3, 1, c)
    set(53 + i * 3, 1, c)
  })
  const fillCell = (i: number, c: number, inset = 0) => {
    const gx = i % GRID
    const gy = Math.floor(i / GRID)
    for (let y = inset; y < CELL - inset; y++)
      for (let x = inset; x < CELL - inset; x++) set(OX + gx * CELL + x, OY + gy * CELL + y, c)
  }
  for (let i = 0; i < GRID * GRID; i++) fillCell(i, L.walls[i] ? C.wall : C.floor)
  fillCell(L.goal, C.goal, 1)
  fillCell(s.pos, C.player, 1)
  if (s.state !== 'NOT_FINISHED') {
    const c = s.state === 'WIN' ? C.win : C.lose
    for (let i = 0; i < FRAME_SIZE; i++) {
      for (let t = 0; t < 2; t++) {
        set(i, OY - 1 + t, c)
        set(i, FRAME_SIZE - 1 - t, c)
        set(t, i < OY - 1 ? -1 : i, c)
        set(FRAME_SIZE - 1 - t, i < OY - 1 ? -1 : i, c)
      }
    }
  }
  return encodeFrame(cells)
}

function newSim(game: MockGame): SimState {
  return { game, level: 0, pos: game.levels[0].start, moves: 0, resets: 0, state: 'NOT_FINISHED', events: [] }
}

function stepSim(s: SimState, action: ActionName) {
  s.events = []
  const L = s.game.levels[s.level]
  if (action === 'RESET') {
    if (s.state === 'WIN') return
    s.pos = L.start
    s.moves = 0
    s.resets++
    s.state = 'NOT_FINISHED'
    s.events.push('reset')
    return
  }
  if (s.state !== 'NOT_FINISHED') return
  const d = DIRS.find((d) => d[0] === action)
  s.moves++
  if (d) {
    const x = (s.pos % GRID) + d[1]
    const y = Math.floor(s.pos / GRID) + d[2]
    const n = y * GRID + x
    if (!L.walls[n]) s.pos = n
    else s.events.push('bump')
  }
  if (s.pos === L.goal) {
    s.events.push('level_complete')
    if (s.level + 1 >= s.game.levels.length) {
      s.state = 'WIN'
    } else {
      s.level++
      s.pos = s.game.levels[s.level].start
      s.moves = 0
    }
  } else if (s.moves >= L.budget) {
    s.state = 'GAME_OVER'
    s.events.push('budget_exhausted')
  }
}

function truthOf(s: SimState): Truth {
  const L = s.game.levels[s.level]
  return {
    state: s.state,
    level: s.level + 1,
    levels_total: s.game.levels.length,
    moves_used: s.moves,
    move_budget: L.budget,
    resets: s.resets,
    active_rules: ['walls', 'goal'],
    new_rule: s.level === 0 ? 'goal' : null,
    events: [...s.events],
    optimal_moves: L.optimal.length,
  }
}

const ACTIONS: ActionName[] = ['RESET', 'ACTION1', 'ACTION2', 'ACTION3', 'ACTION4']

/** Synthesise a plausible model run (optimal path with detours) for replay demos. */
function synthRun(game: MockGame, idx: number): { meta: RunMeta; steps: Step[] } {
  const r = rng(game.meta.seed! + idx * 17)
  const sim = newSim(game)
  const steps: Step[] = []
  let t = 0
  const notes = [
    'The blue square moves with my actions. Green square is probably the target.',
    'Hit a wall, the frame did not change except the yellow bar shrank.',
    'Yellow bar at the top shrinks one notch per action: it looks like a move budget.',
    'Reached green: the layout changed and a pip at the top right turned green. New level.',
  ]
  let i = 0
  while (sim.state === 'NOT_FINISHED' && i < 400) {
    const L = game.levels[sim.level]
    const plan = bfs(L.walls, sim.pos, L.goal) ?? []
    const action: ActionName = r() < 0.25 ? DIRS[Math.floor(r() * 4)][0] : plan[0] ?? 'ACTION1'
    stepSim(sim, action)
    t += 600 + Math.floor(r() * 1800)
    steps.push({
      i,
      t_ms: t,
      action,
      frame: render(sim),
      truth: truthOf(sim),
      reasoning: notes[i % notes.length] + (sim.events.length ? ` (${sim.events.join(', ')})` : ''),
      hypothesis: i < 6 ? 'blue = me, green = goal' : 'reach green before the yellow bar runs out',
      belief: 'playing',
      usage: { in: 1800, out: 120, cost_usd: 0.004 },
      latency_ms: 800 + Math.floor(r() * 1500),
    })
    i++
  }
  const won = sim.state === 'WIN'
  const run_id = `mock-run-${game.meta.seed}-${idx}`
  const tokens_in = steps.length * 1800
  const tokens_out = steps.length * 120
  return {
    steps,
    meta: {
      run_id,
      game_id: game.meta.game_id,
      collection: 'mock',
      player:
        idx === 0
          ? { kind: 'model', name: 'Mock Model A', model_id: 'mock-a', provider: 'mock', effort: 'medium' }
          : { kind: 'model', name: 'Mock Model B', model_id: 'mock-b', provider: 'mock', effort: 'low' },
      harness_version: 'h0',
      started_at: new Date(Date.UTC(2026, 10, 14, 1, idx * 7)).toISOString(),
      ended_at: new Date(Date.UTC(2026, 10, 14, 1, idx * 7) + t).toISOString(),
      outcome: won ? 'WIN' : 'GAME_OVER',
      levels_completed: won ? game.levels.length : sim.level,
      levels_total: game.levels.length,
      actions: steps.length,
      resets: sim.resets,
      tokens_in,
      tokens_out,
      cost_usd: +(steps.length * 0.004).toFixed(4),
      wall_s: Math.round(t / 1000),
    },
  }
}

let synthCache: Record<string, { meta: RunMeta; steps: Step[] }> | null = null
function synthRuns() {
  if (!synthCache) {
    synthCache = {}
    for (const g of MOCK_GAMES)
      for (const idx of [0, 1]) {
        const r = synthRun(g, idx)
        synthCache[r.meta.run_id] = r
      }
  }
  return synthCache
}

const delay = <T>(v: T, ms = 60) => new Promise<T>((res) => setTimeout(() => res(v), ms))

// ---------- Api implementation ----------

export class MockApi implements Api {
  private sessions = new Map<string, { sim: SimState; run: RunMeta; steps: Step[]; t0: number }>()
  private recorded: Record<string, { meta: RunMeta; steps: Step[] }> = {}

  async listGames(collection?: string) {
    const fx = await loadFixtures()
    const all = [...fx.games, ...MOCK_GAMES.map((g) => g.meta)]
    return delay(collection ? all.filter((g) => !g.collection || g.collection === collection) : all)
  }

  async getGame(id: string) {
    const fx = await loadFixtures()
    const g = fx.describes[id] ?? MOCK_GAMES.find((m) => m.meta.game_id === id)?.meta
    if (!g) throw new Error(`mock: unknown game ${id}`)
    return delay(g)
  }

  thumbnailUrl() {
    return null
  }

  /** Mock-only: frame of the first level, used as a thumbnail. */
  previewFrame(gameId: string): Frame | null {
    const g = MOCK_GAMES.find((m) => m.meta.game_id === gameId)
    return g ? render(newSim(g)) : this.fixtureInitial
  }

  private fixtureInitial: Frame | null = null
  constructor() {
    loadFixtures().then((fx) => (this.fixtureInitial = fx.frames.initial ?? null))
  }

  async createSession(body: { game_id: string; player: Player; run_key?: string }): Promise<SessionStart> {
    const g = MOCK_GAMES.find((m) => m.meta.game_id === body.game_id) ?? MOCK_GAMES[0]
    const sim = newSim(g)
    const session_id = `mock-sess-${Math.random().toString(36).slice(2, 10)}`
    const run_id = `mock-live-${session_id.slice(10)}`
    const run: RunMeta = {
      run_id,
      game_id: g.meta.game_id,
      collection: 'mock',
      player: body.player,
      harness_version: 'h0',
      started_at: new Date().toISOString(),
      ended_at: null,
      outcome: null,
      levels_total: g.levels.length,
    }
    const entry = { sim, run, steps: [] as Step[], t0: performance.now() }
    this.sessions.set(session_id, entry)
    this.recorded[run_id] = { meta: run, steps: entry.steps }
    return delay({ session_id, run_id, frame: render(sim), available_actions: ACTIONS })
  }

  async act(id: string, body: ActBody): Promise<ActResponse> {
    const s = this.sessions.get(id)
    if (!s) throw new Error(`mock: unknown session ${id}`)
    stepSim(s.sim, body.action)
    const frame = render(s.sim)
    s.steps.push({
      i: s.steps.length,
      t_ms: Math.round(performance.now() - s.t0),
      action: body.action,
      frame,
      truth: truthOf(s.sim),
      reasoning: body.reasoning,
      hypothesis: body.hypothesis,
      belief: body.belief,
    })
    s.run.actions = s.steps.length
    s.run.levels_completed = s.sim.state === 'WIN' ? s.sim.game.levels.length : s.sim.level
    s.run.resets = s.sim.resets
    return delay({ frame, available_actions: ACTIONS }, 10)
  }

  async truth(id: string) {
    const s = this.sessions.get(id)
    if (!s) throw new Error(`mock: unknown session ${id}`)
    return truthOf(s.sim)
  }

  async endSession(id: string, reason: string) {
    const s = this.sessions.get(id)
    if (!s) return
    s.run.ended_at = new Date().toISOString()
    s.run.outcome = s.sim.state === 'WIN' ? 'WIN' : s.sim.state === 'GAME_OVER' ? 'GAME_OVER' : 'ABORTED'
    s.run.reason = reason
    this.sessions.delete(id)
  }

  async listRuns(q: RunsQuery = {}) {
    const fx = await loadFixtures()
    const metas = [
      ...Object.values(this.recorded).map((r) => r.meta),
      ...Object.values(fx.runs).map((r) => r.meta),
      ...Object.values(synthRuns()).map((r) => r.meta),
    ]
    return delay(
      metas.filter(
        (m) =>
          (!q.game_id || m.game_id === q.game_id) &&
          (!q.model_id || m.player?.model_id === q.model_id) &&
          (!q.kind || m.player?.kind === q.kind),
      ),
    )
  }

  async getRun(id: string) {
    const fx = await loadFixtures()
    const m = this.recorded[id]?.meta ?? fx.runs[id]?.meta ?? synthRuns()[id]?.meta
    if (!m) throw new Error(`mock: unknown run ${id}`)
    return delay(m)
  }

  async getRunSteps(id: string) {
    if (this.recorded[id]) return delay([...this.recorded[id].steps])
    const fx = await loadFixtures()
    const f = fx.runs[id]
    if (f?.stepsPath) return parseAny(await fixtureLoaders[f.stepsPath]()) as Step[]
    const s = synthRuns()[id]
    if (!s) throw new Error(`mock: no steps for run ${id}`)
    return delay(s.steps)
  }

  async derived<T>(name: string): Promise<T> {
    const fx = await loadFixtures()
    const key = fx.derived[name]
    if (!key) throw new Error(`mock: no fixture data/fixtures/derived/${name}.json yet`)
    return parseAny(await fixtureLoaders[key]()) as T
  }

  liveUrl() {
    return null
  }
}
