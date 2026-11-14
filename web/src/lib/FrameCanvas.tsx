import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import { decodeFrame, FRAME_SIZE } from './frame'
import { PALETTE_RGB } from './palette'
import type { Frame } from './types'

interface Props {
  frame: Frame | null | undefined
  /** Integer pixels per frame cell, or 'fit' to fill the parent at the largest integer scale. */
  scale?: number | 'fit'
  /** Minimum scale in fit mode. */
  minScale?: number
  maxScale?: number
  /** In fit mode, also keep the frame inside the viewport height, leaving this many px below it. Null disables. */
  viewportReserve?: number | null
  /** Draw 1px lines between frame cells (debug / gallery detail). */
  grid?: boolean
  /** Absolutely positioned layer above the frame, same size (e.g. truth overlay, path). */
  overlay?: ReactNode
  /** Recessed #080809 cartridge bezel around the 64x64 canvas (DESIGN.md §1, §5). */
  bezel?: boolean
  /** Show 0..63 mono pixel-coordinate rulers + hover (x, y) readout matching model reasoning coordinates. */
  rulers?: boolean
  /** Draggable X-Ray split percentage (0..100). Null/undefined disables split curtain. */
  xraySplit?: number | null
  /** Callback when the user drags or nudges the #ffdc00 X-Ray divider. */
  onXraySplitChange?: (pct: number) => void
  /** Ground-truth SVG CAD overlay revealed on the right side of the X-Ray curtain. */
  xrayOverlay?: ReactNode
  className?: string
  label?: string
}

const RULER_TICKS = [0, 8, 16, 24, 32, 40, 48, 56, 63]
const RULER_GUTTER = 20
const BEZEL_PAD = 6

/**
 * Crisp 64×64 frame renderer. Draws at device-pixel resolution with integer
 * scale so cells never blur. Supports optional cartridge bezel, 0..63 rulers,
 * and a draggable 1px #ffdc00 Physics X-Ray curtain (DESIGN.md §1, §5).
 */
export function FrameCanvas({
  frame,
  scale = 'fit',
  minScale = 2,
  maxScale = 16,
  viewportReserve = null,
  grid = false,
  overlay,
  bezel = false,
  rulers = false,
  xraySplit = null,
  onXraySplitChange,
  xrayOverlay,
  className,
  label = 'Game frame',
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [fitScale, setFitScale] = useState(typeof scale === 'number' ? scale : 6)
  const [hoverCell, setHoverCell] = useState<{ x: number; y: number; colorIdx: number } | null>(null)
  const draggingRef = useRef(false)

  const chromeExtra = (rulers ? RULER_GUTTER : 0) + (bezel ? BEZEL_PAD * 2 : 0)

  useLayoutEffect(() => {
    if (scale !== 'fit') return
    const el = wrapRef.current?.parentElement
    if (!el) return
    const measure = () => {
      const cs = getComputedStyle(el)
      const w = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - chromeExtra
      let s = Math.floor(w / FRAME_SIZE)
      if (viewportReserve != null) {
        const top = el.getBoundingClientRect().top + window.scrollY
        const avail = window.innerHeight - Math.min(top, window.innerHeight / 3) - viewportReserve - chromeExtra
        s = Math.min(s, Math.floor(avail / FRAME_SIZE))
      }
      setFitScale(Math.max(minScale, Math.min(maxScale, s || minScale)))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    window.addEventListener('resize', measure)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [scale, minScale, maxScale, viewportReserve, chromeExtra])

  const s = typeof scale === 'number' ? scale : fitScale
  const cssSize = FRAME_SIZE * s
  const cellsRef = useRef<Uint8Array>(new Uint8Array(FRAME_SIZE * FRAME_SIZE))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = Math.max(1, Math.round(window.devicePixelRatio || 1))
    const px = s * dpr
    const size = FRAME_SIZE * px
    if (canvas.width !== size) {
      canvas.width = size
      canvas.height = size
    }
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const cells = decodeFrame(frame)
    cellsRef.current = cells
    const img = ctx.createImageData(size, size)
    const data = img.data
    for (let cy = 0; cy < FRAME_SIZE; cy++) {
      for (let cx = 0; cx < FRAME_SIZE; cx++) {
        const [r, g, b] = PALETTE_RGB[cells[cy * FRAME_SIZE + cx]] ?? [0, 0, 0]
        for (let yy = 0; yy < px; yy++) {
          let o = ((cy * px + yy) * size + cx * px) * 4
          for (let xx = 0; xx < px; xx++) {
            data[o] = r
            data[o + 1] = g
            data[o + 2] = b
            data[o + 3] = 255
            o += 4
          }
        }
      }
    }
    ctx.putImageData(img, 0, 0)
    if (grid && px >= 4) {
      ctx.fillStyle = 'rgba(140,140,148,0.22)'
      for (let i = 1; i < FRAME_SIZE; i++) {
        ctx.fillRect(i * px, 0, 1, size)
        ctx.fillRect(0, i * px, size, 1)
      }
    }
  }, [frame, s, grid])

  const updateSplitFromClientX = (clientX: number) => {
    const st = stageRef.current
    if (!st || !onXraySplitChange) return
    const rect = st.getBoundingClientRect()
    if (rect.width <= 0) return
    const pct = Math.max(0, Math.min(100, Math.round(((clientX - rect.left) / rect.width) * 100)))
    onXraySplitChange(pct)
  }

  const onStagePointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (draggingRef.current) {
      updateSplitFromClientX(e.clientX)
    }
    if (!rulers) return
    const st = stageRef.current
    if (!st) return
    const rect = st.getBoundingClientRect()
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * FRAME_SIZE)
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * FRAME_SIZE)
    if (x >= 0 && x < FRAME_SIZE && y >= 0 && y < FRAME_SIZE) {
      setHoverCell({ x, y, colorIdx: cellsRef.current[y * FRAME_SIZE + x] ?? 0 })
    } else {
      setHoverCell(null)
    }
  }

  const onHandlePointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!onXraySplitChange) return
    e.preventDefault()
    e.stopPropagation()
    draggingRef.current = true
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const onHandlePointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    draggingRef.current = false
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      /* ignore */
    }
  }

  const onHandleKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (xraySplit == null || !onXraySplitChange) return
    const step = e.shiftKey ? 10 : 2
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      onXraySplitChange(Math.max(0, xraySplit - step))
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      onXraySplitChange(Math.min(100, xraySplit + step))
    } else if (e.key === 'Home') {
      e.preventDefault()
      onXraySplitChange(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      onXraySplitChange(100)
    }
  }

  const showXray = xraySplit != null && !!xrayOverlay

  const innerStage = (
    <div
      ref={stageRef}
      onPointerMove={rulers || showXray ? onStagePointerMove : undefined}
      onPointerLeave={rulers ? () => setHoverCell(null) : undefined}
      style={{
        position: 'relative',
        width: cssSize,
        height: cssSize,
        flex: 'none',
        outline: bezel ? '1px solid var(--line-strong)' : '1px solid var(--line)',
        background: '#000000',
        userSelect: 'none',
      }}
    >
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={label}
        style={{ display: 'block', width: cssSize, height: cssSize, imageRendering: 'pixelated' }}
      />
      {overlay && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>{overlay}</div>
      )}
      {showXray && (
        <>
          <div
            style={{
              position: 'absolute',
              inset: 0,
              pointerEvents: 'none',
              clipPath: `inset(0 0 0 ${xraySplit}%)`,
            }}
          >
            {xrayOverlay}
          </div>
          {xraySplit > 14 && (
            <span
              className="mono"
              style={{
                position: 'absolute',
                top: 4,
                left: 4,
                padding: '1px 5px',
                fontSize: 10,
                lineHeight: '14px',
                background: '#080809',
                border: '1px solid var(--line-strong)',
                color: 'var(--text-2)',
                pointerEvents: 'none',
              }}
            >
              MODEL PIXELS
            </span>
          )}
          {xraySplit < 86 && (
            <span
              className="mono"
              style={{
                position: 'absolute',
                top: 4,
                right: 4,
                padding: '1px 5px',
                fontSize: 10,
                lineHeight: '14px',
                background: '#080809',
                border: '1px solid var(--accent)',
                color: 'var(--accent)',
                pointerEvents: 'none',
              }}
            >
              ENGINE TRUTH · HIDDEN
            </span>
          )}
          <div
            role="slider"
            tabIndex={0}
            aria-label="Physics X-Ray split curtain"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={xraySplit}
            onPointerDown={onHandlePointerDown}
            onPointerMove={(e) => draggingRef.current && updateSplitFromClientX(e.clientX)}
            onPointerUp={onHandlePointerUp}
            onPointerCancel={onHandlePointerUp}
            onKeyDown={onHandleKeyDown}
            title="Drag left/right to compare raw agent pixels vs hidden engine physics"
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${xraySplit}%`,
              width: 16,
              marginLeft: -8,
              cursor: onXraySplitChange ? 'ew-resize' : 'default',
              touchAction: 'none',
              zIndex: 3,
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: 7,
                width: 1,
                background: 'var(--accent)',
              }}
            />
            <div
              className="mono"
              style={{
                position: 'absolute',
                top: '50%',
                left: 0,
                transform: 'translateY(-50%)',
                width: 16,
                height: 26,
                lineHeight: '24px',
                textAlign: 'center',
                fontSize: 9,
                background: '#080809',
                border: '1px solid var(--accent)',
                color: 'var(--accent)',
              }}
            >
              ¦
            </div>
          </div>
        </>
      )}
      {rulers && hoverCell && (
        <>
          <div
            style={{
              position: 'absolute',
              left: hoverCell.x * s,
              top: hoverCell.y * s,
              width: s,
              height: s,
              outline: '1px solid var(--accent)',
              pointerEvents: 'none',
            }}
          />
          <span
            className="mono"
            style={{
              position: 'absolute',
              bottom: 4,
              left: 4,
              padding: '1px 5px',
              fontSize: 10,
              lineHeight: '14px',
              background: '#080809',
              border: '1px solid var(--line-strong)',
              color: 'var(--text-1)',
              pointerEvents: 'none',
              zIndex: 4,
            }}
          >
            ({hoverCell.x}, {hoverCell.y}) · idx {hoverCell.colorIdx}
          </span>
        </>
      )}
    </div>
  )

  if (!bezel && !rulers) {
    return (
      <div ref={wrapRef} className={className} style={{ flex: 'none' }}>
        {innerStage}
      </div>
    )
  }

  return (
    <div
      ref={wrapRef}
      className={className}
      style={{
        flex: 'none',
        padding: bezel ? BEZEL_PAD : 0,
        background: bezel ? '#080809' : 'transparent',
        border: bezel ? '1px solid var(--line-strong)' : undefined,
        display: 'inline-block',
      }}
    >
      {rulers ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `${RULER_GUTTER}px ${cssSize}px`,
            gridTemplateRows: `${RULER_GUTTER - 2}px ${cssSize}px`,
          }}
        >
          <span
            className="mono"
            style={{
              fontSize: 9,
              color: 'var(--text-3)',
              lineHeight: `${RULER_GUTTER - 2}px`,
              textAlign: 'center',
            }}
          >
            x\y
          </span>
          <div style={{ position: 'relative', width: cssSize, height: RULER_GUTTER - 2 }}>
            {RULER_TICKS.map((t) => (
              <span
                key={`rx-${t}`}
                className="mono"
                style={{
                  position: 'absolute',
                  left: `${((t + 0.5) / FRAME_SIZE) * 100}%`,
                  bottom: 2,
                  transform: t === 0 ? 'none' : t === 63 ? 'translateX(-100%)' : 'translateX(-50%)',
                  fontSize: 9,
                  lineHeight: 1,
                  color: 'var(--text-3)',
                }}
              >
                {t}
              </span>
            ))}
          </div>
          <div style={{ position: 'relative', width: RULER_GUTTER, height: cssSize }}>
            {RULER_TICKS.map((t) => (
              <span
                key={`ry-${t}`}
                className="mono"
                style={{
                  position: 'absolute',
                  top: `${((t + 0.5) / FRAME_SIZE) * 100}%`,
                  right: 4,
                  transform: t === 0 ? 'none' : t === 63 ? 'translateY(-100%)' : 'translateY(-50%)',
                  fontSize: 9,
                  lineHeight: 1,
                  color: 'var(--text-3)',
                }}
              >
                {t}
              </span>
            ))}
          </div>
          {innerStage}
        </div>
      ) : (
        innerStage
      )}
    </div>
  )
}
