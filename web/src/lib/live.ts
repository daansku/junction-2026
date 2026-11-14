// Live run feed: WS /api/live ({run_id, event, meta} | {run_id, step}) with a
// polling fallback. Used by the spectate wall.
import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { RunMeta, Step } from './types'

export interface LiveRun {
  meta: RunMeta
  step?: Step
  /** ms timestamp of the last message for this run */
  seen: number
  ended: boolean
}

type Msg = { run_id: string; event?: 'started' | 'ended'; meta?: RunMeta; step?: Step }

/** A run counts as live if it is IN_PROGRESS and started within this window (abandoned runs never end). */
const FRESH_MS = 30 * 60_000
/** Ended runs stay on the wall this long so viewers see the outcome. */
const LINGER_MS = 90_000

export function useLiveRuns(): { runs: LiveRun[]; status: 'connecting' | 'live' | 'polling'; error: unknown } {
  const [runs, setRuns] = useState<Map<string, LiveRun>>(new Map())
  const [status, setStatus] = useState<'connecting' | 'live' | 'polling'>('connecting')
  // Last failure to reach the server; null once any request (or the websocket) succeeds.
  const [error, setError] = useState<unknown>(null)
  const runsRef = useRef(runs)
  runsRef.current = runs

  const apply = (msgs: Msg[]) =>
    setRuns((prev) => {
      const next = new Map(prev)
      const now = Date.now()
      for (const m of msgs) {
        const cur = next.get(m.run_id)
        if (m.event === 'started' && m.meta) next.set(m.run_id, { meta: m.meta, step: cur?.step, seen: now, ended: false })
        else if (m.event === 'ended' && m.meta) next.set(m.run_id, { meta: m.meta, step: cur?.step, seen: now, ended: true })
        else if (m.step) {
          const meta = cur?.meta ?? ({ run_id: m.run_id, game_id: '?', player: { kind: 'model', name: '…' } } as RunMeta)
          if (!cur?.step || (m.step.i ?? 0) >= (cur.step.i ?? 0)) next.set(m.run_id, { meta, step: m.step, seen: now, ended: !!cur?.ended })
        }
      }
      for (const [id, r] of next) if (r.ended && now - r.seen > LINGER_MS) next.delete(id)
      return next
    })

  // seed with runs already in progress
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const metas = await api.listRuns()
        setError(null)
        const now = Date.now()
        const live = metas.filter(
          (m) => m.outcome === 'IN_PROGRESS' && m.started_at && now - Date.parse(m.started_at) < FRESH_MS,
        )
        if (cancelled) return
        apply(live.map((meta) => ({ run_id: meta.run_id, event: 'started' as const, meta })))
        for (const meta of live.slice(0, 24)) {
          api
            .getRunSteps(meta.run_id)
            .then((steps) => {
              const last = steps[steps.length - 1]
              if (!cancelled && last) apply([{ run_id: meta.run_id, step: last }])
            })
            .catch(() => {})
        }
      } catch (e) {
        if (!cancelled) setError(e)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  // websocket with reconnect; fall back to polling when WS is unavailable
  useEffect(() => {
    const url = api.liveUrl()
    let ws: WebSocket | null = null
    let retry = 0
    let stopped = false
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const startPolling = () => {
      if (pollTimer) return
      setStatus('polling')
      pollTimer = setInterval(async () => {
        try {
          const metas = await api.listRuns()
          setError(null)
          const now = Date.now()
          const msgs: Msg[] = []
          for (const m of metas) {
            const known = runsRef.current.get(m.run_id)
            const fresh = m.started_at && now - Date.parse(m.started_at) < FRESH_MS
            if (m.outcome === 'IN_PROGRESS' && fresh) msgs.push({ run_id: m.run_id, event: 'started', meta: m })
            else if (known && !known.ended && m.outcome !== 'IN_PROGRESS') msgs.push({ run_id: m.run_id, event: 'ended', meta: m })
          }
          apply(msgs)
          for (const m of msgs.filter((x) => x.event === 'started').slice(0, 12)) {
            const steps = await api.getRunSteps(m.run_id)
            const last = steps[steps.length - 1]
            if (last) apply([{ run_id: m.run_id, step: last }])
          }
        } catch (e) {
          setError(e) // keep polling
        }
      }, 3000)
    }

    const connect = () => {
      if (!url || stopped) return startPolling()
      ws = new WebSocket(url)
      ws.onopen = () => {
        retry = 0
        setStatus('live')
        setError(null)
        if (pollTimer) {
          clearInterval(pollTimer)
          pollTimer = null
        }
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as Msg
          if (msg && msg.run_id) apply([msg])
        } catch {
          /* ignore malformed */
        }
      }
      ws.onclose = () => {
        if (stopped) return
        retry++
        if (retry >= 3) startPolling()
        reconnectTimer = setTimeout(connect, Math.min(10_000, 500 * 2 ** retry))
      }
    }
    connect()
    return () => {
      stopped = true
      ws?.close()
      if (pollTimer) clearInterval(pollTimer)
      if (reconnectTimer) clearTimeout(reconnectTimer)
    }
  }, [])

  // drop lingering ended runs even without new messages
  useEffect(() => {
    const t = setInterval(() => apply([]), 10_000)
    return () => clearInterval(t)
  }, [])

  const list = [...runs.values()].sort(
    (a, b) =>
      Number(a.ended) - Number(b.ended) ||
      (a.meta.player?.kind === 'model' ? 0 : 1) - (b.meta.player?.kind === 'model' ? 0 : 1) ||
      (a.meta.started_at ?? '').localeCompare(b.meta.started_at ?? ''),
  )
  return { runs: list, status, error }
}
