import { useState } from 'react'
import { decodeFrame, FRAME_SIZE } from '@/lib/frame'
import type { Frame, LevelDescribe, Truth } from '@/lib/types'
import { ruleImageUrl } from './epistemicApi'

const HUD_ROWS = 6

function cellGeometry(w: number, h: number) {
  const cs = Math.max(1, Math.min(Math.floor(64 / w), Math.floor((64 - HUD_ROWS) / h)))
  return {
    cs,
    ox: Math.floor((64 - w * cs) / 2),
    oy: HUD_ROWS + Math.floor((64 - HUD_ROWS - h * cs) / 2),
  }
}

/** Estimate moved entity centroid between two consecutive frames in playfield rows (y >= 6). */
function diffCentroid(prev: Frame | undefined, curr: Frame | undefined): [number, number] | null {
  if (!prev || !curr) return null
  const a = decodeFrame(prev)
  const b = decodeFrame(curr)
  let sumX = 0
  let sumY = 0
  let count = 0
  for (let y = HUD_ROWS; y < FRAME_SIZE; y++) {
    for (let x = 0; x < FRAME_SIZE; x++) {
      const idx = y * FRAME_SIZE + x
      if (a[idx] !== b[idx] && b[idx] !== 0) {
        sumX += x + 0.5
        sumY += y + 0.5
        count++
      }
    }
  }
  if (count === 0 || count > 260) return null
  return [sumX / count, sumY / count]
}

function classifyEventTag(events: string[] | undefined): { text: string; color: string } | null {
  if (!events?.length) return null
  if (events.includes('bump')) return { text: 'BUMP', color: 'var(--bad)' }
  if (events.some((e) => e.startsWith('slid'))) return { text: 'SLID', color: 'var(--series-1)' }
  if (events.includes('reset')) return { text: 'RESET', color: 'var(--warn)' }
  if (events.includes('checkpoints_reset')) return { text: 'CP RESET', color: 'var(--bad)' }
  if (events.includes('checkpoint')) return { text: 'CHECKPOINT', color: 'var(--good)' }
  if (events.includes('teleport')) return { text: 'WARP', color: 'var(--series-7)' }
  if (events.includes('picked_key')) return { text: 'KEY', color: 'var(--accent)' }
  if (events.includes('opened_door')) return { text: 'DOOR OPEN', color: 'var(--good)' }
  if (events.includes('pit_filled')) return { text: 'PIT FILLED', color: 'var(--good)' }
  if (events.includes('hurt') || events.includes('enemy_hit') || events.includes('caught'))
    return { text: 'HAZARD', color: 'var(--bad)' }
  if (events.includes('level_complete') || events.includes('game_won'))
    return { text: 'SOLVED', color: 'var(--good)' }
  return { text: events[0].toUpperCase().slice(0, 10), color: 'var(--text-2)' }
}

/**
 * Crisp miniature pixel-art swatch for a mechanic from `rules/img/<rule>.png` (or `.gif`).
 * `rules/img/<rule>.png` is an 800×272 3-panel strip; `mode="icon"` crops the square start tile,
 * while `mode="strip"` renders the full 3-step teaching progression.
 */
export function RuleSprite({
  rule,
  size = 22,
  mode = 'icon',
  animated = false,
}: {
  rule: string
  size?: number
  mode?: 'icon' | 'strip'
  animated?: boolean
}) {
  const [failed, setFailed] = useState(false)
  const url = ruleImageUrl(rule, animated ? 'gif' : 'png')
  if (!url || failed) {
    return (
      <span
        className="mono"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: size,
          height: size,
          border: '1px solid var(--line-strong)',
          background: '#080809',
          fontSize: 9,
          color: 'var(--accent)',
          flex: 'none',
        }}
        title={rule}
      >
        {rule.slice(0, 2).toUpperCase()}
      </span>
    )
  }

  if (mode === 'strip' && !animated) {
    return (
      <img
        src={url}
        alt={`${rule} teaching progression`}
        onError={() => setFailed(true)}
        style={{
          display: 'block',
          width: '100%',
          maxWidth: 320,
          height: 'auto',
          border: '1px solid var(--line-strong)',
          background: '#080809',
          imageRendering: 'pixelated',
        }}
      />
    )
  }

  return (
    <img
      src={url}
      alt={rule}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        objectFit: 'cover',
        objectPosition: 'left center',
        border: '1px solid var(--line-strong)',
        background: '#080809',
        imageRendering: 'pixelated',
        flex: 'none',
      }}
    />
  )
}

/**
 * SVG CAD ground-truth overlay (`ENGINE TRUTH — hidden from agent`) rendered on the right
 * side of FrameCanvas's draggable #ffdc00 X-Ray curtain.
 */
export function XrayOverlay({
  levelDesc,
  truth,
  recentFrames,
  showTrail = true,
}: {
  levelDesc?: LevelDescribe | null
  truth?: Partial<Truth> | null
  /** Up to last 6 consecutive frames ending at the current frame, for the 5-step ghost trail. */
  recentFrames?: Frame[]
  showTrail?: boolean
}) {
  // 1) Optimal BFS path points in 0..64 frame coordinates
  let optPts: Array<[number, number]> = []
  let cs = 4
  const sp = levelDesc?.start_pixel as [number, number, number] | undefined
  const op = levelDesc?.optimal_pixels as Array<[number, number, number]> | undefined
  const geom = levelDesc?.w && levelDesc?.h ? cellGeometry(levelDesc.w, levelDesc.h) : null

  if (sp && op?.length) {
    cs = sp[2] || 4
    optPts = [sp, ...op].map(([x, y, c]) => [x + c / 2, y + c / 2])
  } else if (geom && levelDesc?.start && levelDesc?.optimal_positions?.length) {
    cs = geom.cs
    optPts = [levelDesc.start, ...levelDesc.optimal_positions].map(([x, y]) => [
      geom.ox + (x + 0.5) * geom.cs,
      geom.oy + (y + 0.5) * geom.cs,
    ])
  }

  // 2) Last-5-steps ghost trail from consecutive frames
  const trailPts: Array<[number, number]> = []
  if (showTrail && recentFrames && recentFrames.length >= 2) {
    const tail = recentFrames.slice(-6)
    for (let i = 1; i < tail.length; i++) {
      const pt = diffCentroid(tail[i - 1], tail[i])
      if (pt) trailPts.push(pt)
    }
  }

  const eventTag = classifyEventTag(truth?.events)
  const lastTrail = trailPts[trailPts.length - 1] ?? optPts[0] ?? [32, 34]
  const activeRules = (truth?.active_rules ?? levelDesc?.rules ?? []).filter(
    (r) => r !== 'walls' && r !== 'goal' && r !== 'move_budget',
  )

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <svg viewBox="0 0 64 64" width="100%" height="100%" aria-hidden style={{ display: 'block' }}>
        {/* Dark translucent CAD tint so vector lines read crisply over bright sprites */}
        <rect x={0} y={0} width={64} height={64} fill="rgba(8, 8, 9, 0.28)" />

        {/* HUD boundary line at y=6 */}
        <line
          x1={0}
          y1={HUD_ROWS}
          x2={64}
          y2={HUD_ROWS}
          stroke="var(--line-strong)"
          strokeWidth={0.25}
          strokeDasharray="1,1"
        />

        {/* Logical playfield bounding box + cell grid ticks when w/h known */}
        {geom && levelDesc?.w && levelDesc?.h && (
          <g opacity={0.45}>
            <rect
              x={geom.ox}
              y={geom.oy}
              width={levelDesc.w * geom.cs}
              height={levelDesc.h * geom.cs}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={0.22}
              strokeDasharray="0.8,0.8"
            />
          </g>
        )}

        {/* Optimal BFS shortest path */}
        {optPts.length >= 2 && (
          <g>
            <polyline
              points={optPts.map((p) => p.join(',')).join(' ')}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={Math.max(0.45, cs / 6)}
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity={0.92}
            />
            <circle
              cx={optPts[0][0]}
              cy={optPts[0][1]}
              r={Math.max(0.65, cs / 4)}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={0.35}
            />
            {(() => {
              const [gx, gy] = optPts[optPts.length - 1]
              const r = Math.max(0.9, cs / 3)
              return (
                <g>
                  <rect
                    x={gx - r}
                    y={gy - r}
                    width={r * 2}
                    height={r * 2}
                    fill="none"
                    stroke="var(--good)"
                    strokeWidth={0.4}
                  />
                  <line x1={gx - r * 1.35} y1={gy} x2={gx + r * 1.35} y2={gy} stroke="var(--good)" strokeWidth={0.28} />
                  <line x1={gx} y1={gy - r * 1.35} x2={gx} y2={gy + r * 1.35} stroke="var(--good)" strokeWidth={0.28} />
                </g>
              )
            })()}
          </g>
        )}

        {/* Last-5-steps ghost trail */}
        {trailPts.length >= 1 && (
          <g>
            {trailPts.length >= 2 && (
              <polyline
                points={trailPts.map((p) => p.join(',')).join(' ')}
                fill="none"
                stroke="var(--series-1)"
                strokeWidth={0.4}
                strokeDasharray="0.7,0.7"
              />
            )}
            {trailPts.map(([tx, ty], idx) => {
              const isHead = idx === trailPts.length - 1
              const alpha = 0.35 + ((idx + 1) / trailPts.length) * 0.65
              return (
                <circle
                  key={`tr-${idx}`}
                  cx={tx}
                  cy={ty}
                  r={isHead ? 0.95 : 0.6}
                  fill={isHead ? 'var(--series-1)' : 'none'}
                  stroke="var(--series-1)"
                  strokeWidth={0.35}
                  opacity={alpha}
                />
              )
            })}
          </g>
        )}

        {/* Physics event marker at active centroid */}
        {eventTag && (
          <g>
            <circle
              cx={lastTrail[0]}
              cy={lastTrail[1]}
              r={Math.max(1.4, cs / 2.2)}
              fill="none"
              stroke={eventTag.color}
              strokeWidth={0.45}
            />
          </g>
        )}
      </svg>

      {/* Crisp bottom-right HUD legend for active hidden rules + event pill */}
      <div
        className="mono"
        style={{
          position: 'absolute',
          bottom: 4,
          right: 4,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          flexWrap: 'wrap',
          justifyContent: 'flex-end',
          maxWidth: '92%',
        }}
      >
        {eventTag && (
          <span
            style={{
              padding: '1px 5px',
              fontSize: 10,
              lineHeight: '14px',
              background: '#080809',
              border: `1px solid ${eventTag.color}`,
              color: eventTag.color,
            }}
          >
            {eventTag.text}
          </span>
        )}
        {activeRules.slice(0, 3).map((r) => (
          <span
            key={r}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              padding: '1px 4px',
              fontSize: 10,
              lineHeight: '14px',
              background: '#080809',
              border: '1px solid var(--line-strong)',
              color: 'var(--text-1)',
            }}
          >
            <RuleSprite rule={r} size={12} />
            {r}
          </span>
        ))}
        {levelDesc?.optimal_moves != null && (
          <span
            style={{
              padding: '1px 5px',
              fontSize: 10,
              lineHeight: '14px',
              background: '#080809',
              border: '1px solid var(--accent)',
              color: 'var(--accent)',
            }}
          >
            BFS OPT {levelDesc.optimal_moves}
          </span>
        )}
      </div>
    </div>
  )
}
