// "Can you beat the AI?" kiosk demo (PLAN.md §3.4, A4-20/A4-21). No paid model calls: the AI side is
// recorded runs (ghost slices from /games/{id}/ghosts) and precomputed per-level stats.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { isTyping } from '@/lib/keys'
import { useServerInfo } from '@/lib/server'
import { Button, ErrorState, Kbd } from '@/design/primitives'
import type { ActionName, Frame, Player } from '@/lib/types'
import { fetchGhosts, startSessionWithTakeover, type GhostSlice } from '@/features/play/epistemicApi'
import {
  challengeScore,
  cleanName,
  clearLocalBoard,
  DEFAULT_GAME,
  DEFAULT_LEVELS,
  fetchBoard,
  loadStats,
  NAME_MAX,
  submitScore,
  type BoardEntry,
  type ChallengeStats,
} from './challengeApi'
import { QrCode } from './QrCode'
import './challenge.css'

const KEYMAP: Record<string, ActionName> = {
  ArrowUp: 'ACTION1',
  w: 'ACTION1',
  W: 'ACTION1',
  ArrowDown: 'ACTION2',
  s: 'ACTION2',
  S: 'ACTION2',
  ArrowLeft: 'ACTION3',
  a: 'ACTION3',
  A: 'ACTION3',
  ArrowRight: 'ACTION4',
  d: 'ACTION4',
  D: 'ACTION4',
  ' ': 'ACTION5',
  r: 'RESET',
  R: 'RESET',
}

/** Same input guard as Play: presses during a pending move are dropped, not queued. */
const MOVE_COOLDOWN_MS = 120
/** No input for this long: end any run and go back to the attract loop (PLAN.md §3.4). */
const IDLE_MS = 60_000
const LOOP_FPS = 6

type Phase = 'lobby' | 'playing' | 'done'

interface LevelResult {
  level: number
  solved: boolean
  actions: number
}

interface Outcome {
  results: LevelResult[]
  score: number
  cleared: number
  moves: number
  beat: boolean
  runId: string
  boardSource?: 'server' | 'local'
}

function ghostName(g: GhostSlice): string {
  return g.player?.name || g.player?.model_id || 'model'
}

function hypothesisAt(g: GhostSlice, moves: number): string | null {
  for (let k = Math.min(moves, g.steps.length) - 1; k >= 0; k--) {
    const h = g.steps[k]?.hypothesis
    if (h && h.trim()) return h.trim()
  }
  return null
}

function ghostFrameAt(g: GhostSlice, moves: number): Frame | null {
  const k = Math.min(moves, g.steps.length)
  return (k > 0 ? g.steps[k - 1]?.frame : g.start_frame) ?? g.start_frame ?? null
}

function pct(x: number) {
  return `${Math.round(100 * x)}%`
}

export function ChallengePage({ kiosk = false }: { kiosk?: boolean }) {
  const [params] = useSearchParams()
  const gameId = params.get('game') || DEFAULT_GAME
  const from = Math.max(1, Number(params.get('from')) || 1)
  const nLevels = Math.min(6, Math.max(1, Number(params.get('levels')) || DEFAULT_LEVELS))
  const levelList = useMemo(() => Array.from({ length: nLevels }, (_, i) => from + i), [from, nLevels])
  const lastLevel = from + nLevels - 1
  const server = useServerInfo()

  const statsQ = useQuery({ queryKey: ['challenge-stats', gameId, from], queryFn: () => loadStats(gameId, from), staleTime: Infinity })
  const stats: ChallengeStats | null = statsQ.data ?? null
  const ghostQs = useQueries({
    queries: levelList.map((lv) => ({
      queryKey: ['ghosts', gameId, lv, 'challenge'],
      queryFn: () => fetchGhosts(gameId, lv, 3),
      staleTime: 10 * 60_000,
    })),
  })
  const boardQ = useQuery({ queryKey: ['challenge-board', gameId], queryFn: () => fetchBoard(gameId), refetchInterval: 30_000 })

  const [phase, setPhase] = useState<Phase>('lobby')
  const [name, setName] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [frame, setFrame] = useState<Frame | null>(null)
  const [available, setAvailable] = useState<ActionName[]>([])
  const [level, setLevel] = useState(from)
  const [levelMoves, setLevelMoves] = useState(0)
  const [results, setResults] = useState<LevelResult[]>([])
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [starting, setStarting] = useState(false)

  const sessionRef = useRef<{ id: string; runId: string } | null>(null)
  const levelRef = useRef(from)
  const movesRef = useRef(0)
  const resultsRef = useRef<LevelResult[]>([])
  const busy = useRef(false)
  const lastMoveAt = useRef(0)
  const lastInput = useRef(performance.now())

  const optimal = useMemo(() => {
    if (stats?.optimal_moves?.length === nLevels) return stats.optimal_moves
    return levelList.map((_, i) => ghostQs[i]?.data?.optimal?.actions ?? 0)
  }, [stats, nLevels, levelList, ghostQs])

  const models = useMemo(() => (stats?.players ?? []).filter((p) => p.kind === 'model'), [stats])
  const humans = useMemo(() => (stats?.players ?? []).find((p) => p.kind === 'human') ?? null, [stats])
  const bestModel = useMemo(() => [...models].sort((a, b) => b.mean_score - a.mean_score)[0] ?? null, [models])

  // ---- session lifecycle
  const endSession = useCallback((reason: string): Promise<void> => {
    const s = sessionRef.current
    sessionRef.current = null
    return s ? api.endSession(s.id, reason).catch(() => {}) : Promise.resolve()
  }, [])

  const resetToLobby = useCallback(
    (clearName: boolean) => {
      endSession('idle')
      setPhase('lobby')
      setOutcome(null)
      setFrame(null)
      setResults([])
      setError(null)
      if (clearName) setName('')
    },
    [endSession],
  )

  const finish = useCallback(
    (finalResults: LevelResult[], reason: string) => {
      const s = sessionRef.current
      const ended = endSession(reason)
      const full = levelList.map((lv) => finalResults.find((r) => r.level === lv) ?? { level: lv, solved: false, actions: 0 })
      const score = challengeScore(full, optimal)
      const cleared = full.filter((r) => r.solved).length
      const moves = full.reduce((a, r) => a + r.actions, 0)
      const ghostBest = Math.max(
        0,
        ...Array.from(new Set(ghostQs.flatMap((q) => q.data?.ghosts ?? []).map(ghostName))).map((nm) =>
          challengeScore(
            levelList.map((lv, i) => {
              const g = ghostQs[i]?.data?.ghosts.find((x) => ghostName(x) === nm)
              return { level: lv, solved: !!g?.solved, actions: g?.actions ?? 0 }
            }),
            optimal,
          ),
        ),
      )
      const aiBar = bestModel ? bestModel.mean_score : ghostBest
      const o: Outcome = { results: full, score, cleared, moves, beat: score > aiBar, runId: s?.runId ?? '' }
      setOutcome(o)
      setPhase('done')
      const entry: BoardEntry = {
        name: name || 'visitor',
        levels_completed: cleared,
        actions: moves,
        score,
        beat_ai: o.beat,
        at: new Date().toISOString(),
        run_id: s?.runId ?? null,
      }
      // the server reads the score from the run, so the run must be closed before posting
      ended.then(() => submitScore(gameId, entry)).then((src) => {
        setOutcome((cur) => (cur ? { ...cur, boardSource: src } : cur))
        boardQ.refetch()
      })
    },
    [endSession, levelList, optimal, ghostQs, bestModel, name, gameId, boardQ],
  )

  const start = useCallback(async () => {
    if (starting) return
    setStarting(true)
    setError(null)
    endSession('switched_game')
    try {
      // both tags: A2 suggested `purpose`, A5 was asked for `mode`; analysis drops either
      const player = { kind: 'human', name: name || 'visitor', mode: 'challenge', purpose: 'challenge' } as Player
      const s = await startSessionWithTakeover({ gameId, player, startLevel: from > 1 ? from : undefined })
      sessionRef.current = { id: s.session_id, runId: s.run_id }
      levelRef.current = from
      movesRef.current = 0
      resultsRef.current = []
      busy.current = false
      setFrame(s.frame)
      setAvailable(s.available_actions)
      setLevel(from)
      setLevelMoves(0)
      setResults([])
      setOutcome(null)
      setPhase('playing')
    } catch (e) {
      setError(e)
    } finally {
      setStarting(false)
    }
  }, [starting, endSession, name, gameId, from])

  const act = useCallback(
    (action: ActionName) => {
      const s = sessionRef.current
      if (!s || phase !== 'playing') return
      const now = performance.now()
      if (busy.current || now - lastMoveAt.current < MOVE_COOLDOWN_MS) return
      busy.current = true
      lastMoveAt.current = now
      ;(async () => {
        try {
          const res = await api.act(s.id, { action })
          if (sessionRef.current?.id !== s.id) return
          setFrame(res.frame)
          setAvailable(res.available_actions)
          movesRef.current += 1
          setLevelMoves(movesRef.current)
          const t = await api.truth(s.id)
          if (sessionRef.current?.id !== s.id) return
          if (t.level && t.level !== levelRef.current) {
            resultsRef.current = [...resultsRef.current, { level: levelRef.current, solved: true, actions: movesRef.current }]
            setResults(resultsRef.current)
            levelRef.current = t.level
            movesRef.current = 0
            setLevel(t.level)
            setLevelMoves(0)
          }
          if (t.state === 'WIN' && !resultsRef.current.some((r) => r.level === levelRef.current)) {
            resultsRef.current = [...resultsRef.current, { level: levelRef.current, solved: true, actions: movesRef.current }]
          }
          if (t.state === 'WIN' || levelRef.current > lastLevel) {
            finish(resultsRef.current, 'challenge_done')
          } else if (t.state === 'GAME_OVER') {
            finish([...resultsRef.current, { level: levelRef.current, solved: false, actions: movesRef.current }], 'game_over')
          }
        } catch (e) {
          setError(e)
        } finally {
          busy.current = false
        }
      })()
    },
    [phase, lastLevel, finish],
  )

  const giveUp = useCallback(() => {
    if (phase !== 'playing') return
    finish([...resultsRef.current, { level: levelRef.current, solved: false, actions: movesRef.current }], 'gave_up')
  }, [phase, finish])

  // ---- input + idle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      lastInput.current = performance.now()
      if (isTyping(e.target) && e.key !== 'Enter') return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'Enter' && phase !== 'playing') {
        e.preventDefault()
        start()
        return
      }
      if (phase !== 'playing') return
      const a = KEYMAP[e.key]
      if (!a) return
      e.preventDefault()
      if (available.length && !available.includes(a)) return
      act(a)
    }
    const onPointer = () => {
      lastInput.current = performance.now()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onPointer)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onPointer)
    }
  }, [phase, available, act, start])

  useEffect(() => {
    const id = setInterval(() => {
      if (performance.now() - lastInput.current < IDLE_MS) return
      lastInput.current = performance.now()
      if (phase !== 'lobby' || name) resetToLobby(true)
    }, 2000)
    return () => clearInterval(id)
  }, [phase, name, resetToLobby])

  useEffect(() => {
    const onHide = () => endSession('left_page')
    window.addEventListener('pagehide', onHide)
    return () => {
      window.removeEventListener('pagehide', onHide)
      onHide()
    }
  }, [endSession])

  // ---- attract loop: a recorded model attempt on the first level, then the optimal path
  const loopReels = useMemo(() => {
    const d = ghostQs[0]?.data
    if (!d) return []
    const reels: Array<{ title: string; sub: string; steps: Frame[] }> = []
    const lost = [...d.ghosts].filter((g) => g.steps.some((s) => s.frame)).sort((a, b) => b.actions - a.actions)[0]
    if (lost)
      reels.push({
        title: ghostName(lost),
        sub: lost.solved ? `level ${from} · solved in ${lost.actions} moves` : `level ${from} · ${lost.actions} moves, never solved`,
        steps: [lost.start_frame, ...lost.steps.map((s) => s.frame)].filter((f): f is Frame => !!f).slice(0, 160),
      })
    const opt = d.optimal
    if (opt && opt.steps.some((s) => s.frame))
      reels.push({
        title: 'Optimal path',
        sub: `level ${from} · ${opt.actions} moves`,
        steps: [opt.start_frame, ...opt.steps.map((s) => s.frame)].filter((f): f is Frame => !!f),
      })
    return reels
  }, [ghostQs, from])
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (phase !== 'lobby' || !loopReels.length) return
    const id = setInterval(() => setTick((t) => t + 1), 1000 / LOOP_FPS)
    return () => clearInterval(id)
  }, [phase, loopReels.length])
  const loop = useMemo(() => {
    if (!loopReels.length) return null
    const total = loopReels.reduce((a, r) => a + r.steps.length + LOOP_FPS * 2, 0)
    let t = tick % total
    for (const r of loopReels) {
      const len = r.steps.length + LOOP_FPS * 2 // hold the last frame for 2 s
      if (t < len) return { ...r, frame: r.steps[Math.min(t, r.steps.length - 1)], i: Math.min(t, r.steps.length - 1) }
      t -= len
    }
    return null
  }, [loopReels, tick])

  const shareUrl = useMemo(() => {
    const u = new URL(`${globalThis.location.origin}${import.meta.env.BASE_URL}challenge`)
    params.forEach((v, k) => k !== 'kiosk' && k !== 'api' && u.searchParams.set(k, v))
    return u.toString()
  }, [params])

  const levelIdx = level - from
  const levelGhosts = ghostQs[levelIdx]?.data?.ghosts ?? []
  const levelOpt = optimal[levelIdx] ?? 0
  const board = boardQ.data

  return (
    <div className={kiosk ? 'challenge challenge-kiosk' : 'challenge'}>
      <header className="ch-head">
        <div>
          <h1 className="ch-title">Can you beat the AI?</h1>
          <p className="ch-sub">
            {nLevels} levels. No instructions. Work out the rules from what you see. The AI got the same pixels.
          </p>
        </div>
        <div className="ch-head-right">
          {phase === 'playing' && (
            <ol className="ch-levels mono" aria-label="Level progress">
              {levelList.map((lv) => {
                const r = results.find((x) => x.level === lv)
                return (
                  <li key={lv} className={r ? 'done' : lv === level ? 'now' : ''}>
                    L{lv - from + 1} {r ? `✓ ${r.actions}` : lv === level ? `· ${levelMoves}` : ''}
                  </li>
                )
              })}
            </ol>
          )}
          {kiosk && (
            <Button
              variant="ghost"
              onClick={() => {
                resetToLobby(true)
                setName('')
              }}
              title="End the current game, clear the name, back to the attract screen"
            >
              reset kiosk
            </Button>
          )}
        </div>
      </header>

      {error != null && <ErrorState error={error} retry={() => setError(null)} />}

      {phase === 'lobby' && (
        <div className="ch-grid">
          <div className="ch-stage">
            <FrameCanvas frame={loop?.frame ?? null} scale="fit" maxScale={kiosk ? 13 : 10} viewportReserve={kiosk ? 64 : 120} bezel label="Recorded AI attempt" />
            {loop && (
              <p className="ch-reel mono">
                <span className="ch-reel-name">{loop.title}</span> · {loop.sub} · move {loop.i}
              </p>
            )}
          </div>
          <aside className="ch-side">
            <section className="ch-card">
              <span className="kicker">recorded results on these {nLevels} levels</span>
              {stats ? (
                <div className="ch-facts">
                  {humans && (
                    <div className="ch-fact">
                      <span className="ch-big mono">{pct(humans.cleared_all_rate)}</span>
                      <span>
                        of people cleared all {nLevels} <span className="muted mono">(n={humans.attempts})</span>
                      </span>
                    </div>
                  )}
                  <div className="ch-fact">
                    <span className="ch-big mono">
                      {models.filter((m) => m.cleared_all_rate > 0).length}/{models.length}
                    </span>
                    <span>AI models ever cleared all {nLevels}</span>
                  </div>
                </div>
              ) : (
                <p className="muted">{statsQ.isLoading ? 'Loading…' : 'No precomputed stats for this game; the race still uses recorded runs.'}</p>
              )}
            </section>
            <form
              className="ch-card ch-start"
              onSubmit={(e) => {
                e.preventDefault()
                start()
              }}
            >
              <label className="kicker" htmlFor="ch-name">
                your name for the board (optional)
              </label>
              <input
                id="ch-name"
                className="ch-input"
                value={name}
                maxLength={NAME_MAX}
                autoComplete="off"
                placeholder="visitor"
                onChange={(e) => setName(cleanName(e.target.value))}
              />
              <Button type="submit" variant="primary" disabled={starting} className="ch-go">
                {starting ? 'Starting…' : 'Play'} <Kbd>Enter</Kbd>
              </Button>
              <p className="muted ch-keys">
                <Kbd>←</Kbd>
                <Kbd>↑</Kbd>
                <Kbd>↓</Kbd>
                <Kbd>→</Kbd> move · <Kbd>Space</Kbd> interact · <Kbd>R</Kbd> restart level. Touch controls on phones.
              </p>
            </form>
            <BoardCard board={board?.entries ?? []} source={board?.source} />
            <section className="ch-card ch-qr">
              <QrCode text={shareUrl} size={132} />
              <div>
                <span className="kicker">play on your phone</span>
                <p className="mono ch-url">{shareUrl.replace(/^https?:\/\//, '')}</p>
                {server.published && <p className="muted">Results are frozen; your play is not added to the research data.</p>}
              </div>
            </section>
          </aside>
        </div>
      )}

      {phase === 'playing' && (
        <div className="ch-grid">
          <div className="ch-stage">
            <FrameCanvas frame={frame} scale="fit" maxScale={kiosk ? 13 : 11} viewportReserve={kiosk ? 96 : 120} bezel label="Your game" />
            <div className="ch-dpad" role="group" aria-label="Touch controls">
              <button type="button" className="d-up" onClick={() => act('ACTION1')} aria-label="Up">↑</button>
              <button type="button" className="d-left" onClick={() => act('ACTION3')} aria-label="Left">←</button>
              <button type="button" className="d-right" onClick={() => act('ACTION4')} aria-label="Right">→</button>
              <button type="button" className="d-down" onClick={() => act('ACTION2')} aria-label="Down">↓</button>
              {available.includes('ACTION5') && (
                <button type="button" className="d-act" onClick={() => act('ACTION5')} aria-label="Interact">␣</button>
              )}
              <button type="button" className="d-reset" onClick={() => act('RESET')} aria-label="Restart level">R</button>
            </div>
          </div>
          <aside className="ch-side">
            <section className="ch-card">
              <span className="kicker">
                level {levelIdx + 1} of {nLevels} · you {levelMoves} moves{levelOpt ? ` · optimal ${levelOpt}` : ''}
              </span>
              <p className="muted ch-race-note">The AI's recorded attempts on this level, move for move with you.</p>
              {ghostQs[levelIdx]?.isLoading ? (
                <p className="muted">Loading recorded runs…</p>
              ) : !levelGhosts.length ? (
                <p className="muted">No recorded model run reached this level.</p>
              ) : (
                <div className="ch-ghosts">
                  {levelGhosts.map((g) => {
                    const ended = levelMoves >= g.actions
                    const hyp = hypothesisAt(g, levelMoves)
                    const gf = ghostFrameAt(g, levelMoves)
                    return (
                      <div key={g.run_id ?? ghostName(g)} className="ch-ghost">
                        {gf ? <FrameCanvas frame={gf} scale={2} label={`${ghostName(g)} frame`} /> : <div className="ch-ghost-empty" />}
                        <div className="ch-ghost-meta">
                          <strong>{ghostName(g)}</strong>
                          <span className={`mono ch-ghost-state ${ended ? (g.solved ? 'good' : 'bad') : ''}`}>
                            {ended
                              ? g.solved
                                ? `SOLVED in ${g.actions}`
                                : `NEVER SOLVED · ${g.actions} moves`
                              : `searching · ${Math.min(levelMoves, g.actions)}/${g.solved ? g.actions : '?'}`}
                          </span>
                          {hyp && <p className="ch-hyp mono">“{hyp.length > 160 ? `${hyp.slice(0, 157)}…` : hyp}”</p>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
            <div className="ch-actions">
              <Button variant="ghost" onClick={giveUp} title="End now and see the result">
                give up
              </Button>
            </div>
          </aside>
        </div>
      )}

      {phase === 'done' && outcome && (
        <EndScreen
          outcome={outcome}
          stats={stats}
          optimal={optimal}
          from={from}
          ghostsByLevel={ghostQs.map((q) => q.data?.ghosts ?? [])}
          board={board?.entries ?? []}
          boardSource={board?.source}
          name={name}
          onAgain={start}
        />
      )}

      {kiosk && (
        <footer className="ch-foot muted mono">
          kiosk · idle {IDLE_MS / 1000}s returns here ·{' '}
          <button type="button" className="linklike" onClick={() => clearLocalBoard(gameId)}>
            clear this device's board
          </button>
        </footer>
      )}
    </div>
  )
}

function BoardCard({ board, source, highlight }: { board: BoardEntry[]; source?: 'server' | 'local'; highlight?: string }) {
  return (
    <section className="ch-card">
      <span className="kicker">visitor board{source === 'local' ? ' · this device only' : ''}</span>
      {!board.length ? (
        <p className="muted">No scores yet. Be the first.</p>
      ) : (
        <table className="ch-board mono">
          <thead>
            <tr>
              <th>#</th>
              <th className="l">name</th>
              <th>levels</th>
              <th>moves</th>
              <th className="l">vs AI</th>
            </tr>
          </thead>
          <tbody>
            {board.slice(0, 8).map((e, i) => (
              <tr key={`${e.at}-${i}`} className={highlight && e.at === highlight ? 'me' : ''}>
                <td>{i + 1}</td>
                <td className="l">{e.name}</td>
                <td>{e.levels_completed}</td>
                <td>{e.actions}</td>
                <td className={`l ${e.beat_ai ? 'good' : 'muted'}`}>{e.beat_ai ? 'beat it' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function EndScreen(props: {
  outcome: Outcome
  stats: ChallengeStats | null
  optimal: number[]
  from: number
  ghostsByLevel: GhostSlice[][]
  board: BoardEntry[]
  boardSource?: 'server' | 'local'
  name: string
  onAgain: () => void
}) {
  const { outcome, stats, optimal, from, ghostsByLevel, board, boardSource, onAgain } = props
  const n = optimal.length
  const models = (stats?.players ?? []).filter((p) => p.kind === 'model')
  const humans = (stats?.players ?? []).find((p) => p.kind === 'human')

  // "The AI needed N moves to figure out what you saw in M": biggest gap on a level you solved.
  const insight = useMemo(() => {
    // Prefer "needed N moves for what you saw in M" against a model that did solve the level (largest ratio);
    // fall back to a model that never solved a level you cleared.
    let solvedGap: { text: string; ratio: number } | null = null
    let neverSolved: string | null = null
    outcome.results.forEach((r, i) => {
      if (!r.solved || r.actions <= 0) return
      const lvl = r.level - from + 1
      for (const g of ghostsByLevel[i] ?? []) {
        if (g.solved && g.actions > r.actions) {
          const ratio = g.actions / r.actions
          if (!solvedGap || ratio > solvedGap.ratio)
            solvedGap = { ratio, text: `${ghostName(g)} needed ${g.actions} moves on level ${lvl} to figure out what you saw in ${r.actions}.` }
        } else if (!g.solved && !neverSolved) {
          neverSolved = `${ghostName(g)} never solved level ${lvl} (${g.actions} moves). You did it in ${r.actions}.`
        }
      }
    })
    return (solvedGap as { text: string } | null)?.text ?? neverSolved
  }, [outcome, ghostsByLevel, from])

  return (
    <div className="ch-end">
      <section className={`ch-verdict ${outcome.beat ? 'good' : 'bad'}`}>
        <span className="kicker">{outcome.beat ? 'result · win' : 'result · loss'}</span>
        <h2 className="ch-verdict-line">{outcome.beat ? 'You beat the AI.' : 'The AI wins this round.'}</h2>
        <div className="ch-stats">
          <div>
            <span className="ch-big mono">{outcome.score.toFixed(1)}</span>
            <span className="muted">your score / 100</span>
          </div>
          <div>
            <span className="ch-big mono">
              {outcome.cleared}/{n}
            </span>
            <span className="muted">levels cleared</span>
          </div>
          <div>
            <span className="ch-big mono">{outcome.moves}</span>
            <span className="muted">moves (optimal {optimal.reduce((a, b) => a + b, 0)})</span>
          </div>
        </div>
        {insight && <p className="ch-insight">{insight}</p>}
        <div className="ch-end-actions">
          <Button variant="primary" onClick={onAgain}>
            Play again <Kbd>Enter</Kbd>
          </Button>
          {outcome.runId && <Link to={`/replay/${outcome.runId}`}>watch your replay</Link>}
        </div>
      </section>

      <section className="ch-card">
        <span className="kicker">you vs recorded players · score per level = optimal / your moves, 0 if unsolved</span>
        <table className="ch-table mono">
          <thead>
            <tr>
              <th className="l">player</th>
              {optimal.map((_, i) => (
                <th key={i}>L{i + 1}</th>
              ))}
              <th>score</th>
              <th>attempts</th>
            </tr>
          </thead>
          <tbody>
            <tr className="me">
              <td className="l">You{props.name ? ` (${props.name})` : ''}</td>
              {outcome.results.map((r) => (
                <td key={r.level}>{r.solved ? `${r.actions} mv` : '✗'}</td>
              ))}
              <td>{outcome.score.toFixed(1)}</td>
              <td>1</td>
            </tr>
            <tr>
              <td className="l">Optimal path</td>
              {optimal.map((o, i) => (
                <td key={i}>{o} mv</td>
              ))}
              <td>100.0</td>
              <td>—</td>
            </tr>
            {humans && (
              <tr>
                <td className="l">People (playtests)</td>
                {humans.per_level_solve_rate.map((x, i) => (
                  <td key={i}>{pct(x)} solved</td>
                ))}
                <td>{humans.mean_score.toFixed(1)}</td>
                <td>{humans.attempts}</td>
              </tr>
            )}
            {models.map((m) => (
              <tr key={m.id}>
                <td className="l">{m.name}</td>
                {m.per_level_solve_rate.map((x, i) => (
                  <td key={i}>{pct(x)} solved</td>
                ))}
                <td>{m.mean_score.toFixed(1)}</td>
                <td>{m.attempts}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted ch-note">
          Score and solve rates for people and models are averages over every recorded attempt (h1 harness). You beat the AI when your
          score is above the best model average.
          {stats ? ` Data: ${stats.generated_at.slice(0, 16).replace('T', ' ')} UTC.` : ''}
        </p>
      </section>

      <BoardCard board={board} source={boardSource ?? outcome.boardSource} />
    </div>
  )
}
