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
  CHALLENGE_GAMES,
  challengeScore,
  cleanName,
  clearLocalBoard,
  DEFAULT_GAME,
  DEFAULT_LEVELS,
  fetchBoard,
  fetchChallengeGhosts,
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

type Phase = 'lobby' | 'playing' | 'review' | 'done'

/** Between levels: what happened on the level just played, while the AI's recorded attempts replay. */
interface Review {
  idx: number
  level: number
  kind: 'solved' | 'lost' | 'gaveup'
  actions: number
  /** solved the last level of the challenge (or the whole game) */
  last: boolean
}

/** Replay speed: slow enough to follow each move (human feedback: 10/s was too fast). */
const REVIEW_FPS = 4

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
  let k = Math.min(moves, g.steps.length)
  // the frame after a level's winning move is already the NEXT level: end a solved replay one frame earlier
  if (g.solved && k === g.steps.length) k -= 1
  return (k > 0 ? g.steps[k - 1]?.frame : g.start_frame) ?? g.start_frame ?? null
}

function pct(x: number) {
  return `${Math.round(100 * x)}%`
}

export function ChallengePage({ kiosk = false }: { kiosk?: boolean }) {
  const [params, setParams] = useSearchParams()
  const gameId = params.get('game') || DEFAULT_GAME
  const pickGame = (id: string) =>
    setParams(
      (p) => {
        const n = new URLSearchParams(p)
        if (id === DEFAULT_GAME) n.delete('game')
        else n.set('game', id)
        return n
      },
      { replace: true },
    )
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
      queryFn: () => fetchChallengeGhosts(gameId, lv, 4),
      staleTime: 10 * 60_000,
    })),
  })
  // Opponents shown during play: names only (results would hint at the solution), any model that played this game.
  const opponentsQ = useQuery({
    queryKey: ['challenge-opponents', gameId],
    queryFn: async () => {
      const runs = await api.listRuns({ game_id: gameId, kind: 'model' })
      const by = new Map<string, { name: string; finished: boolean }>()
      for (const r of runs) {
        if (r.outcome === 'ABORTED' || (r as Record<string, unknown>).start_level) continue
        const id = r.player?.model_id || r.player?.name
        if (!id) continue
        const prev = by.get(id)
        const finished = !!r.outcome && r.outcome !== 'IN_PROGRESS'
        by.set(id, { name: r.player?.name || id, finished: finished || !!prev?.finished })
      }
      return [...by.values()].sort((a, b) => Number(b.finished) - Number(a.finished) || a.name.localeCompare(b.name))
    },
    staleTime: 60_000,
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
  const [review, setReview] = useState<Review | null>(null)

  const sessionRef = useRef<{ id: string; runId: string } | null>(null)
  const levelRef = useRef(from)
  const movesRef = useRef(0)
  const resultsRef = useRef<LevelResult[]>([])
  const phaseRef = useRef<Phase>('lobby')
  phaseRef.current = phase
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
      setReview(null)
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
      setReview(null)
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
      if (!s || phaseRef.current !== 'playing') return
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
          const played = levelRef.current
          let solvedActions: number | null = null
          if (t.level && t.level !== played) {
            solvedActions = movesRef.current
            levelRef.current = t.level
            movesRef.current = 0
            setLevel(t.level)
            setLevelMoves(0)
          } else if (t.state === 'WIN' && !resultsRef.current.some((r) => r.level === played)) {
            solvedActions = movesRef.current
          }
          if (solvedActions != null) {
            resultsRef.current = [...resultsRef.current, { level: played, solved: true, actions: solvedActions }]
            setResults(resultsRef.current)
            const last = t.state === 'WIN' || levelRef.current > lastLevel
            setReview({ idx: played - from, level: played, kind: 'solved', actions: solvedActions, last })
            setPhase('review')
          } else if (t.state === 'GAME_OVER') {
            // level lost: the engine keeps the session; RESET restarts this level (and counts as a move, as for models)
            setReview({ idx: played - from, level: played, kind: 'lost', actions: movesRef.current, last: false })
            setPhase('review')
          }
        } catch (e) {
          setError(e)
        } finally {
          busy.current = false
        }
      })()
    },
    [lastLevel, from],
  )

  const giveUp = useCallback(() => {
    if (phaseRef.current !== 'playing') return
    setReview({ idx: levelRef.current - from, level: levelRef.current, kind: 'gaveup', actions: movesRef.current, last: false })
    setPhase('review')
  }, [from])

  const failLevelAndFinish = useCallback(
    (reason: string) => finish([...resultsRef.current, { level: levelRef.current, solved: false, actions: movesRef.current }], reason),
    [finish],
  )

  /** Primary action of the review screen (Enter). */
  const reviewPrimary = useCallback(() => {
    if (!review) return
    if (review.kind === 'solved') {
      if (review.last) finish(resultsRef.current, 'challenge_done')
      else setPhase('playing')
    } else if (review.kind === 'lost') {
      phaseRef.current = 'playing'
      setPhase('playing')
      lastMoveAt.current = 0
      act('RESET')
    } else {
      setPhase('playing')
    }
  }, [review, finish, act])

  const reviewSecondary = useCallback(() => {
    if (!review || review.kind === 'solved') return
    failLevelAndFinish(review.kind === 'lost' ? 'game_over' : 'gave_up')
  }, [review, failLevelAndFinish])

  // ---- input + idle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      lastInput.current = performance.now()
      if (isTyping(e.target) && e.key !== 'Enter') return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (phase === 'review') {
        if (e.key === 'Enter') {
          e.preventDefault()
          reviewPrimary()
        } else if ((e.key === 'r' || e.key === 'R') && review?.kind === 'lost') {
          e.preventDefault()
          reviewPrimary()
        }
        return
      }
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
  }, [phase, available, act, start, review, reviewPrimary])

  useEffect(() => {
    const id = setInterval(() => {
      if (performance.now() - lastInput.current < IDLE_MS) return
      lastInput.current = performance.now()
      if (phase !== 'lobby' || name) resetToLobby(true)
    }, 2000)
    return () => clearInterval(id)
  }, [phase, name, resetToLobby])

  // phones: Play sits below the frame, so a new phase would open scrolled down with the frame cut off
  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [phase])

  useEffect(() => {
    const onHide = () => endSession('left_page')
    window.addEventListener('pagehide', onHide)
    return () => {
      window.removeEventListener('pagehide', onHide)
      onHide()
    }
  }, [endSession])

  // ---- attract loop: a recorded model attempt on the level AFTER the challenge window, so nothing a visitor
  // is about to play is shown (no spoilers). Nothing loops when no model run reached that level.
  const teaserLevel = lastLevel + 1
  const teaserQ = useQuery({
    queryKey: ['ghosts', gameId, teaserLevel, 'challenge'],
    queryFn: () => fetchGhosts(gameId, teaserLevel, 3),
    staleTime: 10 * 60_000,
  })
  const loopReels = useMemo(() => {
    const d = teaserQ.data
    if (!d) return []
    const g = [...d.ghosts].filter((x) => x.steps.some((st) => st.frame)).sort((a, b) => b.actions - a.actions)[0]
    if (!g) return []
    return [
      {
        title: ghostName(g),
        sub: `game level ${teaserLevel} (not part of the challenge) · ${g.solved ? `solved in ${g.actions} moves` : `${g.actions} moves, never solved`}`,
        steps: [g.start_frame, ...g.steps.map((st) => st.frame)].filter((f): f is Frame => !!f).slice(0, 200),
      },
    ]
  }, [teaserQ.data, teaserLevel])
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
          {(phase === 'playing' || phase === 'review') && (
            <ol className="ch-levels mono" aria-label="Level progress">
              {levelList.map((lv) => {
                const r = results.find((x) => x.level === lv)
                return (
                  <li key={lv} className={r ? 'done' : lv === level ? (phase === 'review' && review?.kind !== 'solved' ? 'lost' : 'now') : ''}>
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
            <FrameCanvas frame={loop?.frame ?? ghostQs[0]?.data?.optimal?.start_frame ?? null} scale="fit" maxScale={kiosk ? 13 : 10} viewportReserve={kiosk ? 64 : 120} bezel label="Recorded AI attempt" />
            {loop ? (
              <p className="ch-reel mono">
                <span className="ch-reel-name">{loop.title}</span> · {loop.sub} · move {loop.i}
              </p>
            ) : (
              <p className="ch-reel mono">level 1 · this is where you start</p>
            )}
          </div>
          <aside className="ch-side">
            <section className="ch-card">
              <span className="kicker">pick a game · eval-v1, levels 1–{nLevels}</span>
              <div className="ch-tabs" role="radiogroup" aria-label="Game">
                {CHALLENGE_GAMES.map((g) => (
                  <Button key={g.id} variant="ghost" mono active={g.id === gameId} onClick={() => pickGame(g.id)} role="radio" aria-checked={g.id === gameId} title={g.id}>
                    game {g.label}
                  </Button>
                ))}
                {!CHALLENGE_GAMES.some((g) => g.id === gameId) && <span className="mono muted">{gameId}</span>}
              </div>
            </section>
            <section className="ch-card">
              <span className="kicker">recorded results on these {nLevels} levels</span>
              {stats ? (
                <div className="ch-facts">
                  {humans && (
                    <div className="ch-fact">
                      <span className="ch-big mono">{pct(humans.cleared_all_rate)}</span>
                      <span>
                        of people cleared all {nLevels} <span className="muted mono">(first attempts, n={humans.attempts})</span>
                      </span>
                    </div>
                  )}
                  {models.length ? (
                    <div className="ch-fact">
                      <span className="ch-big mono">
                        {models.filter((m) => m.cleared_all_rate > 0).length}/{models.length}
                      </span>
                      <span>AI models ever cleared all {nLevels}</span>
                    </div>
                  ) : (
                    <p className="muted">No finished AI run on this game yet.</p>
                  )}
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
                level {levelIdx + 1} of {nLevels} · you {levelMoves} moves
              </span>
              <p className="muted ch-race-note">
                No hints. The AI played these same levels from the same pixels; you see its recorded attempts after the challenge.
              </p>
            </section>
            <section className="ch-card">
              <span className="kicker">you are up against</span>
              {opponentsQ.isLoading ? (
                <p className="muted">Loading…</p>
              ) : !opponentsQ.data?.length ? (
                <p className="muted">No AI has played this game yet.</p>
              ) : (
                <ul className="ch-tobeat mono">
                  {opponentsQ.data.slice(0, 8).map((o) => (
                    <li key={o.name}>
                      <span>{o.name}</span>
                      <span className="muted">{o.finished ? 'recorded' : 'still playing'}</span>
                    </li>
                  ))}
                  {opponentsQ.data.length > 8 && (
                    <li>
                      <span className="muted">+{opponentsQ.data.length - 8} more</span>
                      <span />
                    </li>
                  )}
                </ul>
              )}
            </section>
            <div className="ch-actions">
              <Button variant="ghost" onClick={giveUp} title="Stop this level">
                give up
              </Button>
            </div>
          </aside>
        </div>
      )}

      {phase === 'review' && review && (
        <LevelReview
          review={review}
          levelNo={review.idx + 1}
          nLevels={nLevels}
          optimal={optimal[review.idx] ?? 0}
          frame={frame}
          ghosts={ghostQs[review.idx]?.data?.ghosts ?? []}
          optimalGhost={ghostQs[review.idx]?.data?.optimal ?? null}
          onPrimary={reviewPrimary}
          onSecondary={reviewSecondary}
        />
      )}

      {phase === 'done' && outcome && (
        <EndScreen
          outcome={outcome}
          stats={stats}
          optimal={optimal}
          from={from}
          ghostsByLevel={ghostQs.map((q) => q.data?.ghosts ?? [])}
          optimalByLevel={ghostQs.map((q) => q.data?.optimal ?? null)}
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

function Reel({ g, title, tick, scale }: { g: GhostSlice; title: string; tick: number; scale: number }) {
  const n = g.steps.length
  const hold = REVIEW_FPS * 2 // hold the last frame 2 s before looping
  const m = n ? tick % (n + 1 + hold) : 0
  const shown = Math.min(m, n)
  const frame = ghostFrameAt(g, shown)
  const hyp = hypothesisAt(g, shown)
  const ended = shown >= n
  return (
    <figure className="ch-reel-card">
      {frame ? <FrameCanvas frame={frame} scale={scale} label={`${title} replay`} /> : <div className="ch-ghost-empty" />}
      <figcaption className="ch-ghost-meta">
        <strong>{title}</strong>
        <span className={`mono ch-ghost-state ${ended ? (g.solved ? 'good' : 'bad') : ''}`}>
          move {shown}/{n}
          {ended ? (g.solved ? ' · SOLVED' : ' · NEVER SOLVED') : ''}
        </span>
        {/* always rendered at a fixed height so changing model text never moves the layout */}
        <p className="ch-hyp mono" title={hyp ?? undefined}>
          {hyp ? `“${hyp}”` : '\u00a0'}
        </p>
      </figcaption>
    </figure>
  )
}

/** Between levels: your result only. The AI's attempts are shown after the whole challenge (no spoilers). */
function LevelReview(props: {
  review: Review
  levelNo: number
  nLevels: number
  optimal: number
  frame: Frame | null
  ghosts: GhostSlice[]
  optimalGhost: GhostSlice | null
  onPrimary: () => void
  onSecondary: () => void
}) {
  const { review, levelNo, nLevels, optimal, frame, ghosts, optimalGhost, onPrimary, onSecondary } = props
  const headline =
    review.kind === 'solved'
      ? `Level ${levelNo} solved in ${review.actions} moves.`
      : review.kind === 'lost'
        ? `Level ${levelNo} lost after ${review.actions} moves.`
        : `You stopped level ${levelNo} after ${review.actions} moves.`
  const primary =
    review.kind === 'solved' ? (review.last ? 'See results' : `Next level (${levelNo + 1} of ${nLevels})`) : review.kind === 'lost' ? 'Retry level' : 'Keep trying'
  const card = (
    <section className={`ch-verdict ${review.kind === 'solved' ? 'good' : 'bad'}`}>
      <span className="kicker">{review.kind === 'solved' ? 'level solved' : review.kind === 'lost' ? 'level lost' : 'level stopped'}</span>
      <h2 className="ch-review-line">{headline}</h2>
      {review.kind === 'solved' && optimal > 0 && <p className="mono muted">optimal: {optimal} moves</p>}
      {review.kind === 'lost' && (
        <p className="muted">Retry restarts this level. Your moves so far still count, the same rule the models play by.</p>
      )}
      <div className="ch-end-actions">
        <Button variant="primary" onClick={onPrimary}>
          {primary} <Kbd>Enter</Kbd>
        </Button>
        {review.kind !== 'solved' && (
          <Button variant="ghost" onClick={onSecondary}>
            end challenge
          </Button>
        )}
      </div>
    </section>
  )
  return (
    review.kind === 'solved' ? (
      // level done, so its AI attempts can no longer spoil it (lost / stopped levels can be retried: no AI there)
      <div className="ch-grid">
        <section className="ch-card ch-review">
          <span className="kicker">the AI on level {levelNo} · recorded attempts, replayed</span>
          <LevelReels key={review.level} ghosts={ghosts} optimalGhost={optimalGhost} level={levelNo} />
        </section>
        <aside className="ch-side">{card}</aside>
      </div>
    ) : !frame ? (
      // nothing to show beside it: the card takes the main column (an empty frame column left it off-screen)
      <div className="ch-solo">{card}</div>
    ) : (
      <div className="ch-grid">
        <div className="ch-stage">
          <FrameCanvas frame={frame} scale="fit" maxScale={10} viewportReserve={120} bezel label="Your game" />
        </div>
        <aside className="ch-side">{card}</aside>
      </div>
    )
  )
}

/** Every recorded model attempt + the optimal path on one level, replayed in lockstep from move 0. */
function LevelReels({ ghosts, optimalGhost, level }: { ghosts: GhostSlice[]; optimalGhost: GhostSlice | null; level: number }) {
  const [tick, setTick] = useState(0)
  // restarts from move 0 on mount; callers remount with `key` to restart (array props are not stable refs)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000 / REVIEW_FPS)
    return () => clearInterval(id)
  }, [])
  const reels = [
    ...ghosts.filter((g) => g.steps.length).map((g) => ({ g, title: ghostName(g) })),
    ...(optimalGhost?.steps.some((s) => s.frame) ? [{ g: optimalGhost, title: 'Optimal path' }] : []),
  ]
  return (
    <>
      {!ghosts.length && (
        <p className="muted">No finished AI run on level {level} of this game yet{reels.length ? '; the optimal path is shown.' : '.'}</p>
      )}
      {!!reels.length && (
        <div className="ch-reels">
          {reels.map((r) => (
            <Reel key={`${level}-${r.g.run_id ?? r.title}`} g={r.g} title={r.title} tick={tick} scale={4} />
          ))}
        </div>
      )}
    </>
  )
}

/** After the challenge: every recorded model attempt + the optimal path, one level at a time. */
function AiReplays({ levels, from }: { levels: Array<{ ghosts: GhostSlice[]; optimal: GhostSlice | null }>; from: number }) {
  const [sel, setSel] = useState(0)
  const cur = levels[sel] ?? { ghosts: [], optimal: null }
  return (
    <section className="ch-card ch-review">
      <div className="ch-review-head">
        <span className="kicker">how the AI played · recorded attempts, replayed</span>
        <div className="ch-tabs" role="tablist">
          {levels.map((_, i) => (
            <Button key={i} variant="ghost" mono active={i === sel} onClick={() => setSel(i)} role="tab" aria-selected={i === sel}>
              L{i + 1}
            </Button>
          ))}
        </div>
      </div>
      <LevelReels key={sel} ghosts={cur.ghosts} optimalGhost={cur.optimal} level={sel + 1} />
      <p className="muted ch-note">Level numbers are within this challenge (game levels {from}–{from + levels.length - 1}).</p>
    </section>
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
  optimalByLevel: Array<GhostSlice | null>
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
      <section className={`ch-verdict ch-a-verdict ${outcome.beat ? 'good' : 'bad'}`}>
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

      <section className="ch-card ch-a-table">
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
                <td className="l">People (first attempts)</td>
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

      <div className="ch-a-board">
        <BoardCard board={board} source={boardSource ?? outcome.boardSource} />
      </div>

      {/* right under the verdict so it is on screen at 1080p without scrolling */}
      <div className="ch-a-replays">
        <AiReplays levels={ghostsByLevel.map((g, i) => ({ ghosts: g, optimal: props.optimalByLevel[i] ?? null }))} from={from} />
      </div>
    </div>
  )
}
