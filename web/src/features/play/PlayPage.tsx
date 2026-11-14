import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { API } from '@/lib/config'
import { FrameCanvas } from '@/lib/FrameCanvas'
import { isTyping } from '@/lib/keys'
import type { ActionName, Frame, GameMeta, Truth } from '@/lib/types'
import { Button, Chip, ErrorState, Kbd, Loading, PageHeader, Panel, Stat } from '@/design/primitives'
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

interface Session {
  id: string
  runId: string
  gameId: string
}

export function PlayPage() {
  const { gameId: routeGame } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()

  const collections = useQuery({ queryKey: ['collections'], queryFn: () => api.listCollections() })
  const collection = params.get('collection') ?? (collections.data?.includes('dev') ? 'dev' : collections.data?.[0])
  const games = useQuery({
    queryKey: ['games', collection],
    queryFn: () => api.listGames(collection),
    enabled: collections.isFetched,
  })
  const gameId = routeGame ?? games.data?.[0]?.game_id

  const [name, setName] = useState(loadName)
  const [session, setSession] = useState<Session | null>(null)
  const [frame, setFrame] = useState<Frame | null>(null)
  const [available, setAvailable] = useState<ActionName[]>([])
  const [log, setLog] = useState<ActionName[]>([])
  const [error, setError] = useState<unknown>(null)
  const [showTruth, setShowTruth] = useState(false)
  const [truth, setTruth] = useState<Truth | null>(null)
  const [finished, setFinished] = useState<Truth | null>(null)
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const sessionRef = useRef<Session | null>(null)
  sessionRef.current = session

  const endCurrent = useCallback((reason: string) => {
    const s = sessionRef.current
    if (s) api.endSession(s.id, reason).catch(() => {})
    sessionRef.current = null
  }, [])

  const start = useCallback(async () => {
    if (!gameId) return
    blurActive()
    setError(null)
    endCurrent('restarted')
    try {
      try {
        localStorage.setItem('playerName', name)
      } catch {
        /* ignore */
      }
      const res = await api.createSession({
        game_id: gameId,
        player: { kind: 'human', name: name.trim() || 'anonymous' },
      })
      const s = { id: res.session_id, runId: res.run_id, gameId }
      sessionRef.current = s
      setSession(s)
      setFrame(res.frame)
      setAvailable(res.available_actions)
      setLog([])
      setTruth(null)
      setFinished(null)
    } catch (e) {
      setError(e)
    }
  }, [gameId, name, endCurrent])

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
      queue.current = queue.current.then(async () => {
        if (sessionRef.current?.id !== s.id) return
        try {
          const res = await api.act(s.id, { action })
          setFrame(res.frame)
          setAvailable(res.available_actions)
          setLog((l) => [...l, action])
          // Truth is fetched for the end-of-game summary and the optional debug panel;
          // the player only ever sees the frame while playing.
          const t = await api.truth(s.id)
          setTruth(t)
          if (t.state === 'WIN') {
            setFinished(t)
            api.endSession(s.id, 'won').catch(() => {})
            sessionRef.current = null
          }
        } catch (e) {
          setError(e)
        }
      })
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

  const pickGame = (id: string) => {
    endCurrent('switched_game')
    setSession(null)
    setFrame(null)
    setFinished(null)
    blurActive()
    navigate({ pathname: `/play/${encodeURIComponent(id)}`, search: params.toString() })
  }

  const isShared = API.mode === 'shared' || API.mode === 'same-origin' || API.mode === 'custom'
  const resets = log.filter((a) => a === 'RESET').length

  return (
    <>
      <PageHeader
        title="Play"
        sub="You see exactly the frame a model sees. No rules, no score. Work it out."
        actions={
          <>
            <label className="field">
              <span className="kicker">name</span>
              <input
                type="text"
                value={name}
                placeholder="your name"
                onChange={(e) => setName(e.target.value)}
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
                {games.data?.map((g) => (
                  <option key={g.game_id} value={g.game_id}>
                    {gameLabel(g)}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="primary" onClick={start} disabled={!gameId}>
              {session ? 'Restart run' : 'Start'}
            </Button>
          </>
        }
      />
      {games.error ? <ErrorState error={games.error} retry={() => games.refetch()} /> : null}
      {error ? <ErrorState error={error} /> : null}

      <div className="play-grid">
        <div className="play-stage">
          {frame ? (
            <div className="play-frame-wrap">
              <FrameCanvas frame={frame} scale="fit" maxScale={12} label="Game frame" />
              {finished && (
                <div className="play-done" role="status">
                  <Chip outcome="WIN">ALL LEVELS SOLVED</Chip>
                  <div className="play-done-stats">
                    <Stat label="actions" value={log.length} />
                    <Stat label="resets" value={resets} />
                    <Stat label="levels" value={finished.levels_total} />
                  </div>
                  <div className="play-done-actions">
                    {session && (
                      <Link to={`/replay/${encodeURIComponent(session.runId)}`}>Watch your replay</Link>
                    )}
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
            <button type="button" className="play-start" onClick={start} disabled={!gameId}>
              <span>Press</span> <Kbd>Enter</Kbd> <span>or click to start</span>
            </button>
          )}
        </div>

        <aside className="play-side">
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
            {isShared && (
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
            {session && log.length > 0 && (
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
                <dd>{truth.active_rules?.join(', ') || '—'}</dd>
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
