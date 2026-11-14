import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { API } from '@/lib/config'
import { useServerInfo } from '@/lib/server'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { isTyping } from '@/lib/keys'
import type { ActionName, Frame, GameMeta, Truth } from '@/lib/types'
import { Button, Chip, ErrorState, Kbd, Loading, PageHeader, Panel, Stat } from '@/design/primitives'
import { NewGamePanel, parseGameId } from './NewGamePanel'
import { fetchGhosts, startSessionWithTakeover, type GhostSlice } from './epistemicApi'
import { RuleSprite, XrayOverlay } from './XrayOverlay'
import './play.css'

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

const LABEL: Record<string, string> = {
  RESET: 'R',
  ACTION1: '↑',
  ACTION2: '↓',
  ACTION3: '←',
  ACTION4: '→',
  ACTION5: '␣',
}

/** Minimum time between two moves, on top of waiting for the previous move's frame. */
const MOVE_COOLDOWN_MS = 120

function loadName() {
  try {
    return localStorage.getItem('playerName') ?? ''
  } catch {
    return ''
  }
}

function gameLabel(g: GameMeta) {
  const lv = g.levels_total ?? g.spec?.n_levels ?? g.n_levels
  const d = g.difficulty ?? g.spec?.difficulty
  return `${g.game_id}${d != null ? `  ·  d${d}` : ''}${lv ? `  ·  ${lv} lv` : ''}`
}

function blurActive() {
  const el = document.activeElement as HTMLElement | null
  if (el && el !== document.body) el.blur()
}

function ghostTitle(g: GhostSlice): string {
  const base = g.player?.name || g.player?.model_id || 'model'
  return g.player?.effort ? `${base} · ${g.player.effort}` : base
}

function latestHypothesisAt(g: GhostSlice, moveIdx: number): string | null {
  if (moveIdx <= 0 || !g.steps.length) return null
  const cap = Math.min(moveIdx - 1, g.steps.length - 1)
  for (let k = cap; k >= 0; k--) {
    const h = g.steps[k]?.hypothesis
    if (h && h.trim()) return h.trim()
  }
  return null
}

interface Session {
  id: string
  runId: string
  gameId: string
  isTakeover?: boolean
  fallbackLevel1?: boolean
}

export function PlayPage() {
  const { gameId: routeGame } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const server = useServerInfo()

  const takeoverRun = params.get('takeover_run')
  const takeoverStep = params.get('takeover_step') != null ? Number(params.get('takeover_step')) : null
  const takeoverLevel = params.get('takeover_level') != null ? Math.max(1, Number(params.get('takeover_level'))) : null
  const takeoverPlayer = params.get('takeover_model')
  const isTakeoverMode = !!takeoverRun

  const collections = useQuery({ queryKey: ['collections'], queryFn: () => api.listCollections() })
  const collection = params.get('collection') ?? (collections.data?.includes('dev') ? 'dev' : collections.data?.[0])
  const games = useQuery({
    queryKey: ['games', collection],
    queryFn: () => api.listGames(collection),
    enabled: collections.isFetched,
  })
  const gameId = routeGame ?? games.data?.[0]?.game_id

  const [name, setName] = useState(loadName)
  const [nameMissing, setNameMissing] = useState(false)
  const nameRef = useRef<HTMLInputElement>(null)
  const isShared = API.mode === 'shared' || API.mode === 'same-origin' || API.mode === 'custom'
  // Runs on the shared server are the human baseline: they need a name to be attributable (except take-overs).
  const nameRequired = isShared && !server.published && !isTakeoverMode

  const [session, setSession] = useState<Session | null>(null)
  const [frame, setFrame] = useState<Frame | null>(null)
  const [recentFrames, setRecentFrames] = useState<Frame[]>([])
  const [available, setAvailable] = useState<ActionName[]>([])
  const [log, setLog] = useState<ActionName[]>([])
  const [currentLevel, setCurrentLevel] = useState<number>(takeoverLevel ?? 1)
  const [levelMoveCount, setLevelMoveCount] = useState<number>(0)
  const [error, setError] = useState<unknown>(null)

  // Cartridge & Epistemic Arena controls (X-Ray and Truth off by default so baseline runs stay unspoiled)
  const [showRulers, setShowRulers] = useState(false)
  const [showGrid, setShowGrid] = useState(false)
  const [showTruth, setShowTruth] = useState(false)
  const [xraySplit, setXraySplit] = useState<number | null>(null)
  const [ghostRaceOn, setGhostRaceOn] = useState(true)

  const [truth, setTruth] = useState<Truth | null>(null)
  const [finished, setFinished] = useState<Truth | null>(null)

  const moveBusy = useRef(false)
  const lastMoveAt = useRef(0)
  const truthSeq = useRef(0)
  const levelRef = useRef<number>(takeoverLevel ?? 1)
  const sessionRef = useRef<Session | null>(null)
  sessionRef.current = session

  const endCurrent = useCallback((reason: string) => {
    const s = sessionRef.current
    if (s) api.endSession(s.id, reason).catch(() => {})
    sessionRef.current = null
  }, [])

  const start = useCallback(
    async (overrideTakeover?: { runId: string; step: number; level: number } | null) => {
      if (!gameId) return
      const tk =
        overrideTakeover !== undefined
          ? overrideTakeover
          : takeoverRun
            ? { runId: takeoverRun, step: takeoverStep ?? 0, level: takeoverLevel ?? 1 }
            : null

      if (!tk && nameRequired && !name.trim()) {
        setNameMissing(true)
        nameRef.current?.focus()
        return
      }
      setNameMissing(false)
      blurActive()
      moveBusy.current = false
      setError(null)
      endCurrent('restarted')
      try {
        if (name.trim()) {
          try {
            localStorage.setItem('playerName', name)
          } catch {
            /* ignore */
          }
        }
        const res = await startSessionWithTakeover({
          gameId,
          player: {
            kind: 'human',
            name: tk ? name.trim() || 'test' : name.trim() || 'anonymous',
          },
          startLevel: tk?.level,
          takeoverOf: tk ? { run_id: tk.runId, step: tk.step } : undefined,
        })
        const initLv = res.fallbackLevel1 ? 1 : (tk?.level ?? 1)
        const s: Session = {
          id: res.session_id,
          runId: res.run_id,
          gameId,
          isTakeover: !!tk,
          fallbackLevel1: res.fallbackLevel1,
        }
        sessionRef.current = s
        levelRef.current = initLv
        setSession(s)
        setFrame(res.frame)
        setRecentFrames([res.frame])
        setAvailable(res.available_actions)
        setLog([])
        setCurrentLevel(initLv)
        setLevelMoveCount(0)
        setTruth(null)
        setFinished(null)
      } catch (e) {
        setError(e)
      }
    },
    [gameId, name, nameRequired, endCurrent, takeoverRun, takeoverStep, takeoverLevel],
  )

  // Auto-launch when arriving via `[ TAKE OVER FROM STEP N ]`
  const autoLaunchedTakeover = useRef<string | null>(null)
  useEffect(() => {
    if (!gameId || !takeoverRun) return
    const key = `${gameId}:${takeoverRun}:${takeoverStep ?? 0}:${takeoverLevel ?? 1}`
    if (autoLaunchedTakeover.current === key) return
    autoLaunchedTakeover.current = key
    start({ runId: takeoverRun, step: takeoverStep ?? 0, level: takeoverLevel ?? 1 })
  }, [gameId, takeoverRun, takeoverStep, takeoverLevel, start])

  // Close the run when leaving the page or the tab.
  useEffect(() => {
    const onUnload = () => endCurrent('left_page')
    window.addEventListener('pagehide', onUnload)
    return () => {
      window.removeEventListener('pagehide', onUnload)
      onUnload()
    }
  }, [endCurrent])

  const act = useCallback(
    (action: ActionName) => {
      const s = sessionRef.current
      if (!s || finished) return
      const now = performance.now()
      if (moveBusy.current || now - lastMoveAt.current < MOVE_COOLDOWN_MS) return
      moveBusy.current = true
      lastMoveAt.current = now
      ;(async () => {
        try {
          const res = await api.act(s.id, { action })
          if (sessionRef.current?.id !== s.id) return
          setFrame(res.frame)
          setRecentFrames((prev) => [...prev.slice(-5), res.frame])
          setAvailable(res.available_actions)
          setLog((l) => [...l, action])
          setLevelMoveCount((c) => c + 1)
          const seq = ++truthSeq.current
          api
            .truth(s.id)
            .then((t) => {
              if (seq !== truthSeq.current && t.state !== 'WIN') return
              setTruth(t)
              if (t.level && t.level !== levelRef.current) {
                levelRef.current = t.level
                setCurrentLevel(t.level)
                setLevelMoveCount(0)
                setRecentFrames([res.frame])
              }
              if (t.state === 'WIN' && sessionRef.current?.id === s.id) {
                setFinished(t)
                api.endSession(s.id, 'won').catch(() => {})
                sessionRef.current = null
              }
            })
            .catch((e) => setError(e))
        } catch (e) {
          setError(e)
        } finally {
          if (sessionRef.current?.id === s.id || !sessionRef.current) moveBusy.current = false
        }
      })()
    },
    [finished],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'Enter' && (!sessionRef.current || finished)) {
        e.preventDefault()
        start()
        return
      }
      const a = KEYMAP[e.key]
      if (!a) return
      e.preventDefault()
      if (available.length && !available.includes(a)) return
      act(a)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [act, available, start, finished])

  // Fetch full describe ONLY when X-Ray Curtain is explicitly enabled (playtester debug / takeover)
  const gameDesc = useQuery({
    queryKey: ['game', gameId],
    queryFn: () => api.getGame(gameId!),
    enabled: !!gameId && xraySplit != null,
  })
  const levelDesc = gameDesc.data?.levels?.find((l) => l.level === currentLevel) ?? null

  // Fetch lockstep ghosts for current game + level
  const ghostsQ = useQuery({
    queryKey: ['ghosts', gameId, currentLevel],
    queryFn: () => fetchGhosts(gameId!, currentLevel, 3),
    enabled: !!gameId && ghostRaceOn,
    staleTime: 60_000,
  })

  // Human baseline = first attempt only: mark games this player already played on this server.
  const me = name.trim().toLowerCase()
  const myRuns = useQuery({
    queryKey: ['runs', 'human-mine'],
    queryFn: () => api.listRuns({ kind: 'human' }),
    enabled: nameRequired && !!me && me !== 'test',
    staleTime: 20_000,
    refetchInterval: 60_000,
  })
  const played = useMemo(
    () =>
      new Set(
        (myRuns.data ?? [])
          .filter((r) => (r.player?.name ?? '').trim().toLowerCase() === me && (r.actions ?? 0) > 0)
          .map((r) => r.game_id),
      ),
    [myRuns.data, me],
  )
  const nextUnplayed = games.data?.find((g) => !played.has(g.game_id) && g.game_id !== gameId)?.game_id

  const pickGame = (id: string) => {
    if (nameRequired && me && me !== 'test') myRuns.refetch()
    endCurrent('switched_game')
    setSession(null)
    setFrame(null)
    setFinished(null)
    blurActive()
    const cleanParams = new URLSearchParams(params)
    cleanParams.delete('takeover_run')
    cleanParams.delete('takeover_step')
    cleanParams.delete('takeover_level')
    cleanParams.delete('takeover_model')
    navigate({ pathname: `/play/${encodeURIComponent(id)}`, search: cleanParams.toString() })
  }

  const exitTakeover = () => {
    const clean = new URLSearchParams(params)
    clean.delete('takeover_run')
    clean.delete('takeover_step')
    clean.delete('takeover_level')
    clean.delete('takeover_model')
    setParams(clean, { replace: true })
  }

  const pendingStart = useRef<string | null>(null)
  const onGenerated = (id: string) => {
    pendingStart.current = id
    pickGame(id)
  }
  useEffect(() => {
    if (gameId && pendingStart.current === gameId) {
      pendingStart.current = null
      start(null)
    }
  }, [gameId, start])

  const ident = parseGameId(gameId)
  const listed = !!games.data?.some((g) => g.game_id === gameId)
  const [copied, setCopied] = useState(false)
  const copyLink = () => {
    if (!gameId) return
    const url = `${window.location.origin}/play/${encodeURIComponent(gameId)}`
    navigator.clipboard?.writeText(url).then(
      () => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      },
      () => {},
    )
  }

  const resets = log.filter((a) => a === 'RESET').length
  const modelGhosts = ghostsQ.data?.ghosts ?? []
  const optGhost = ghostsQ.data?.optimal ?? null

  return (
    <>
      <PageHeader
        title="Play"
        sub="You see the exact 64×64 frame a model sees. No rules, no score. Reverse-engineer the physics."
        actions={
          <>
            <label className="field">
              <span className="kicker">name</span>
              <input
                ref={nameRef}
                type="text"
                value={name}
                placeholder={nameRequired ? 'your name (required)' : 'your name'}
                aria-invalid={nameMissing || undefined}
                onChange={(e) => {
                  setName(e.target.value)
                  if (e.target.value.trim()) setNameMissing(false)
                }}
                onKeyDown={(e) => e.key === 'Enter' && start()}
              />
            </label>
            {(collections.data?.length ?? 0) > 1 && (
              <label className="field">
                <span className="kicker">set</span>
                <select
                  value={collection ?? ''}
                  onChange={(e) => {
                    endCurrent('switched_game')
                    setSession(null)
                    setFrame(null)
                    blurActive()
                    navigate({ pathname: '/play', search: `collection=${encodeURIComponent(e.target.value)}` })
                  }}
                >
                  {collections.data!.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="field">
              <span className="kicker">game</span>
              <select value={gameId ?? ''} onChange={(e) => pickGame(e.target.value)}>
                {gameId && games.data && !listed && (
                  <option value={gameId}>
                    {ident ? `new game · seed ${ident.seed} · d${ident.difficulty} · ${ident.levels} lv` : gameId}
                  </option>
                )}
                {games.data?.map((g) => (
                  <option key={g.game_id} value={g.game_id}>
                    {gameLabel(g)}
                    {played.has(g.game_id) ? '  ·  played' : ''}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="primary" onClick={() => start()} disabled={!gameId}>
              {session ? 'Restart run' : 'Start'}
            </Button>
          </>
        }
      />

      {games.error ? <ErrorState error={games.error} retry={() => games.refetch()} /> : null}
      {error ? <ErrorState error={error} /> : null}

      {isTakeoverMode && takeoverRun && (
        <div className="play-takeover-banner mono" role="status">
          <span>
            <Chip outcome="BUDGET">TAKE-OVER</Chip>{' '}
            Resumed {takeoverPlayer ? <strong>{takeoverPlayer}</strong> : 'model run'} on{' '}
            <strong>Level {takeoverLevel ?? 1}</strong>
            {takeoverStep != null ? ` (from step ${takeoverStep})` : ''}. Excluded from the human baseline.
            {session?.fallbackLevel1 ? ' · Server pre-restart: started from Level 1.' : ''}
          </span>
          <span className="play-takeover-links">
            <Link to={`/replay/${encodeURIComponent(takeoverRun)}${takeoverStep != null ? `?step=${takeoverStep}` : ''}`}>
              ← Back to replay
            </Link>
            <button type="button" className="linklike" onClick={exitTakeover}>
              Standard mode
            </button>
          </span>
        </div>
      )}

      {gameId && played.has(gameId) && !session && !isTakeoverMode ? (
        <p className="play-name-missing" role="status">
          You already played this game as <span className="mono">{name.trim()}</span>. Only your first attempt counts
          for the human baseline.{' '}
          {nextUnplayed ? (
            <button type="button" className="linklike" onClick={() => pickGame(nextUnplayed)}>
              Go to the next game you haven&apos;t played
            </button>
          ) : (
            'You have played every game in this set.'
          )}
        </p>
      ) : null}

      {nameMissing ? (
        <p className="play-name-missing" role="alert">
          Enter your name first: runs here are recorded as the human baseline. Practising? Use{' '}
          <span className="mono">test</span>.
        </p>
      ) : null}

      <div className="play-grid">
        <div className="play-stage">
          {frame ? (
            <div className="play-frame-wrap">
              <div className="cartridge-bar mono">
                <span className="muted">
                  L{currentLevel} · move {levelMoveCount}
                  {optGhost ? ` · opt ${optGhost.actions}` : ''}
                </span>
                <div className="cartridge-toggles">
                  <Button
                    variant="ghost"
                    mono
                    active={showRulers}
                    onClick={() => setShowRulers((v) => !v)}
                    title="Toggle 0..63 pixel coordinate rulers"
                  >
                    rulers
                  </Button>
                  <Button
                    variant="ghost"
                    mono
                    active={showGrid}
                    onClick={() => setShowGrid((v) => !v)}
                    title="Toggle 64×64 pixel cell grid"
                  >
                    grid
                  </Button>
                  <Button
                    variant="ghost"
                    mono
                    active={xraySplit != null}
                    onClick={() => setXraySplit((cur) => (cur == null ? 50 : null))}
                    title="Debug X-Ray split curtain (spoils hidden rules)"
                  >
                    x-ray {xraySplit != null ? `${xraySplit}%` : 'off'}
                  </Button>
                </div>
              </div>

              <FrameCanvas
                frame={frame}
                scale="fit"
                maxScale={11}
                viewportReserve={68}
                bezel
                rulers={showRulers}
                grid={showGrid}
                xraySplit={xraySplit}
                onXraySplitChange={setXraySplit}
                xrayOverlay={
                  xraySplit != null ? (
                    <XrayOverlay levelDesc={levelDesc} truth={truth} recentFrames={recentFrames} />
                  ) : undefined
                }
                label="Game frame"
              />

              <div className="dpad" aria-label="On-screen controls">
                <button type="button" className="dpad-up" onClick={() => act('ACTION1')} aria-label="Up">↑</button>
                <button type="button" className="dpad-left" onClick={() => act('ACTION3')} aria-label="Left">←</button>
                <button type="button" className="dpad-right" onClick={() => act('ACTION4')} aria-label="Right">→</button>
                <button type="button" className="dpad-down" onClick={() => act('ACTION2')} aria-label="Down">↓</button>
                {available.includes('ACTION5') && (
                  <button type="button" className="dpad-act" onClick={() => act('ACTION5')} aria-label="Interact">␣</button>
                )}
                <button type="button" className="dpad-reset" onClick={() => act('RESET')} aria-label="Restart level">R</button>
              </div>

              {finished && (
                <div className="play-done" role="status">
                  <Chip outcome="WIN">ALL LEVELS SOLVED</Chip>
                  <div className="play-done-stats">
                    <Stat label="actions" value={log.length} />
                    <Stat label="resets" value={resets} />
                    <Stat label="levels" value={finished.levels_total} />
                  </div>
                  <div className="play-done-actions">
                    {session && !server.published && (
                      <Link to={`/replay/${encodeURIComponent(session.runId)}`}>Watch your replay</Link>
                    )}
                    {server.published && <Link to="/replay">Watch how the models did</Link>}
                    <span className="muted">
                      <Kbd>Enter</Kbd> play again
                    </span>
                  </div>
                </div>
              )}
            </div>
          ) : games.isLoading || collections.isLoading ? (
            <Loading what="Loading games" />
          ) : (
            <button type="button" className="play-start" onClick={() => start()} disabled={!gameId}>
              <span>Press</span> <Kbd>Enter</Kbd> <span>or click to start</span>
            </button>
          )}
        </div>

        <aside className="play-side">
          <Panel
            label={`ghost race · L${currentLevel} lockstep`}
            actions={
              <Button variant="ghost" mono active={ghostRaceOn} onClick={() => setGhostRaceOn((v) => !v)}>
                {ghostRaceOn ? 'on' : 'off'}
              </Button>
            }
          >
            {!ghostRaceOn ? (
              <span className="muted">Paused. Enable to step recorded frontier models alongside each keypress.</span>
            ) : ghostsQ.isLoading ? (
              <span className="muted mono">Loading level L{currentLevel} traces…</span>
            ) : !modelGhosts.length && !optGhost ? (
              <span className="muted">
                Fresh world — no recorded model runs on this seed yet. You are setting the first trace.
              </span>
            ) : (
              <div className="ghost-list">
                {optGhost && (
                  <div className="ghost-pace mono">
                    <span>
                      <strong>BFS optimal</strong> · {optGhost.actions} moves
                    </span>
                    <span className={levelMoveCount <= optGhost.actions ? 'ghost-ahead' : 'muted'}>
                      {levelMoveCount === 0
                        ? 'ready'
                        : levelMoveCount <= optGhost.actions
                          ? `you ${levelMoveCount}/${optGhost.actions}`
                          : `+${levelMoveCount - optGhost.actions} over opt`}
                    </span>
                  </div>
                )}
                {modelGhosts.map((g) => {
                  const idx = Math.min(Math.max(0, levelMoveCount - 1), Math.max(0, g.steps.length - 1))
                  const gStep = levelMoveCount > 0 ? g.steps[idx] : null
                  const gFrame = levelMoveCount === 0 ? g.start_frame : (gStep?.frame ?? g.start_frame)
                  const finishedAt = levelMoveCount >= g.actions
                  const hyp = latestHypothesisAt(g, levelMoveCount)
                  const bumped = gStep?.events?.includes('bump')

                  return (
                    <div key={g.run_id ?? ghostTitle(g)} className="ghost-card">
                      <div className="ghost-card-top">
                        {gFrame ? (
                          <FrameCanvas frame={gFrame} scale={1} label={`${ghostTitle(g)} ghost frame`} />
                        ) : (
                          <div className="ghost-no-frame mono">64²</div>
                        )}
                        <div className="ghost-meta">
                          <div className="ghost-name-row">
                            <strong className="ghost-name">{ghostTitle(g)}</strong>
                            <Chip outcome={finishedAt ? (g.solved ? 'WIN' : 'BUDGET') : bumped ? 'GAME_OVER' : 'NOT_FINISHED'}>
                              {finishedAt
                                ? g.solved
                                  ? `SOLVED @${g.actions}`
                                  : `STALLED @${g.actions}`
                                : levelMoveCount === 0
                                  ? `${g.actions} act`
                                  : `step ${Math.min(levelMoveCount, g.actions)}/${g.actions}`}
                            </Chip>
                          </div>
                          <div className="mono muted ghost-sub">
                            {gStep ? (
                              <>
                                act <span className="secondary">{LABEL[gStep.action] ?? gStep.action}</span>
                                {gStep.events?.length ? ` · ${gStep.events.slice(0, 2).join(', ')}` : ''}
                              </>
                            ) : (
                              <span>Moves 1 step per keypress</span>
                            )}
                            {g.run_id && (
                              <>
                                {' · '}
                                <Link
                                  to={`/replay/${encodeURIComponent(g.run_id)}${g.first_step != null ? `?step=${g.first_step + idx}` : ''}`}
                                >
                                  replay →
                                </Link>
                              </>
                            )}
                          </div>
                          {hyp && <p className="mono ghost-hyp">“{hyp}”</p>}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Panel>

          <NewGamePanel onGenerated={onGenerated} />

          {ident && (
            <Panel label="this game">
              <div className="game-ident">
                <span className="mono">
                  seed <strong>{ident.seed}</strong> · d{ident.difficulty} · {ident.levels} levels
                </span>
                <Button variant="ghost" onClick={copyLink} title="Copy a link that opens this exact game">
                  {copied ? 'Copied' : 'Copy link'}
                </Button>
              </div>
            </Panel>
          )}

          <Panel label="controls">
            <div className="controls">
              <span>
                <Kbd>↑</Kbd>
                <Kbd>↓</Kbd>
                <Kbd>←</Kbd>
                <Kbd>→</Kbd> or <Kbd>W</Kbd>
                <Kbd>A</Kbd>
                <Kbd>S</Kbd>
                <Kbd>D</Kbd> move
              </span>
              {available.includes('ACTION5') && (
                <span>
                  <Kbd>Space</Kbd> interact
                </span>
              )}
              <span>
                <Kbd>R</Kbd> restart level (counts as an action)
              </span>
            </div>
            {isShared && !server.published && !isTakeoverMode && (
              <p className="muted play-note">
                Runs on this server are recorded as the human baseline under your name. Practising? Use name{' '}
                <span className="mono">test</span>.
              </p>
            )}
          </Panel>

          <Panel
            label={`actions · ${log.length}`}
            actions={session && <span className="mono muted">run {session.runId.slice(-8)}</span>}
          >
            {log.length ? (
              <div className="action-log mono">
                {log.slice(-160).map((a, i) => (
                  <span key={i} className={a === 'RESET' ? 'log-reset' : undefined}>
                    {LABEL[a] ?? a}
                  </span>
                ))}
              </div>
            ) : (
              <span className="muted">No actions yet.</span>
            )}
            {session && log.length > 0 && !server.published && (
              <div style={{ marginTop: 8 }}>
                <Link to={`/replay/${encodeURIComponent(session.runId)}`}>Open this run in replay</Link>
              </div>
            )}
          </Panel>

          <Panel
            label="truth · hidden from agents"
            actions={
              <Button variant="ghost" mono active={showTruth} onClick={() => setShowTruth((v) => !v)}>
                {showTruth ? 'on' : 'off'}
              </Button>
            }
          >
            {showTruth && truth ? (
              <dl className="truth mono">
                <dt>state</dt>
                <dd>
                  <Chip outcome={truth.state} />
                </dd>
                <dt>level</dt>
                <dd>
                  {truth.level} / {truth.levels_total}
                </dd>
                <dt>moves</dt>
                <dd>
                  {truth.moves_used} / {truth.move_budget} (opt {truth.optimal_moves})
                </dd>
                <dt>resets</dt>
                <dd>{truth.resets}</dd>
                <dt>rules</dt>
                <dd className="truth-rules">
                  {truth.active_rules?.length
                    ? truth.active_rules.map((r) => (
                        <span key={r} className="truth-rule-pill">
                          <RuleSprite rule={r} size={14} />
                          {r}
                        </span>
                      ))
                    : '—'}
                </dd>
                <dt>new</dt>
                <dd>{truth.new_rule ?? '—'}</dd>
                <dt>events</dt>
                <dd>{truth.events?.join(', ') || '—'}</dd>
              </dl>
            ) : showTruth ? (
              <span className="muted">Make a move to load truth.</span>
            ) : (
              <span className="muted">Debug overlay for playtesters. Off by default. Spoils the rules.</span>
            )}
          </Panel>
        </aside>
      </div>
    </>
  )
}
