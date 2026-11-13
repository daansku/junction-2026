import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { FrameCanvas } from '@/lib/FrameCanvas'
import type { ActionName, Frame, Truth } from '@/lib/types'
import { Button, Chip, ErrorState, Kbd, Loading, PageHeader, Panel } from '@/design/primitives'
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

interface Session {
  id: string
  runId: string
  gameId: string
}

export function PlayPage() {
  const { gameId: routeGame } = useParams()
  const navigate = useNavigate()
  const games = useQuery({ queryKey: ['games'], queryFn: () => api.listGames() })
  const gameId = routeGame ?? games.data?.[0]?.game_id

  const [name, setName] = useState(loadName)
  const [session, setSession] = useState<Session | null>(null)
  const [frame, setFrame] = useState<Frame | null>(null)
  const [available, setAvailable] = useState<ActionName[]>([])
  const [log, setLog] = useState<ActionName[]>([])
  const [error, setError] = useState<unknown>(null)
  const [showTruth, setShowTruth] = useState(false)
  const [truth, setTruth] = useState<Truth | null>(null)
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const sessionRef = useRef<Session | null>(null)
  sessionRef.current = session

  const start = useCallback(async () => {
    if (!gameId) return
    setError(null)
    const prev = sessionRef.current
    if (prev) api.endSession(prev.id, 'restarted').catch(() => {})
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
      setSession({ id: res.session_id, runId: res.run_id, gameId })
      setFrame(res.frame)
      setAvailable(res.available_actions)
      setLog([])
      setTruth(null)
    } catch (e) {
      setError(e)
    }
  }, [gameId, name])

  // End the run when leaving the page.
  useEffect(
    () => () => {
      const s = sessionRef.current
      if (s) api.endSession(s.id, 'left_page').catch(() => {})
    },
    [],
  )

  const refreshTruth = useCallback(async (s: Session) => {
    try {
      setTruth(await api.truth(s.id))
    } catch {
      /* debug only */
    }
  }, [])

  const act = useCallback(
    (action: ActionName) => {
      const s = sessionRef.current
      if (!s) return
      queue.current = queue.current.then(async () => {
        try {
          const res = await api.act(s.id, { action })
          setFrame(res.frame)
          setAvailable(res.available_actions)
          setLog((l) => [...l, action])
          if (showTruth) refreshTruth(s)
        } catch (e) {
          setError(e)
        }
      })
    },
    [showTruth, refreshTruth],
  )

  useEffect(() => {
    if (showTruth && session) refreshTruth(session)
  }, [showTruth, session, refreshTruth])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t.closest('input, textarea, select')) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const a = KEYMAP[e.key]
      if (!a) {
        if (e.key === 'Enter' && !sessionRef.current) start()
        return
      }
      e.preventDefault()
      if (available.length && !available.includes(a)) return
      act(a)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [act, available, start])

  return (
    <>
      <PageHeader
        title="Play"
        sub="You see exactly the frame a model sees. No rules, no score — work it out."
        actions={
          <>
            <label className="field">
              <span className="kicker">name</span>
              <input type="text" value={name} placeholder="your name" onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="field">
              <span className="kicker">game</span>
              <select
                value={gameId ?? ''}
                onChange={(e) => {
                  setSession(null)
                  setFrame(null)
                  navigate(`/play/${encodeURIComponent(e.target.value)}`)
                }}
              >
                {games.data?.map((g) => (
                  <option key={g.game_id} value={g.game_id}>
                    {g.game_id}
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
            <FrameCanvas frame={frame} scale="fit" maxScale={12} label="Game frame" />
          ) : games.isLoading ? (
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
              <span>
                <Kbd>Space</Kbd> interact
              </span>
              <span>
                <Kbd>R</Kbd> restart level (counts as an action)
              </span>
            </div>
          </Panel>

          <Panel
            label={`actions · ${log.length}`}
            actions={session && <span className="mono muted">run {session.runId.slice(0, 12)}</span>}
          >
            {log.length ? (
              <div className="action-log mono">
                {log.slice(-120).map((a, i) => (
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
            label="truth — hidden from agents"
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
                <dd>{truth.active_rules.join(', ')}</dd>
                <dt>new</dt>
                <dd>{truth.new_rule ?? '—'}</dd>
                <dt>events</dt>
                <dd>{truth.events.join(', ') || '—'}</dd>
              </dl>
            ) : (
              <span className="muted">Debug overlay for playtesters. Off by default.</span>
            )}
          </Panel>
        </aside>
      </div>
    </>
  )
}
