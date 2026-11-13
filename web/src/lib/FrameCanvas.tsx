import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
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
  /** Draw 1px lines between frame cells (debug / gallery detail). */
  grid?: boolean
  /** Absolutely positioned layer above the frame, same size (e.g. truth overlay, path). */
  overlay?: ReactNode
  className?: string
  label?: string
}

/**
 * Crisp 64×64 frame renderer. Draws at device-pixel resolution with integer
 * scale so cells never blur. DESIGN.md §1, §5.
 */
export function FrameCanvas({
  frame,
  scale = 'fit',
  minScale = 2,
  maxScale = 16,
  grid = false,
  overlay,
  className,
  label = 'Game frame',
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [fitScale, setFitScale] = useState(typeof scale === 'number' ? scale : 6)

  useLayoutEffect(() => {
    if (scale !== 'fit') return
    const el = wrapRef.current?.parentElement
    if (!el) return
    const measure = () => {
      // Width only: the parent's height usually depends on the canvas itself.
      const cs = getComputedStyle(el)
      const w = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
      const s = Math.floor(w / FRAME_SIZE)
      setFitScale(Math.max(minScale, Math.min(maxScale, s || minScale)))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [scale, minScale, maxScale])

  const s = typeof scale === 'number' ? scale : fitScale
  const cssSize = FRAME_SIZE * s

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
      ctx.fillStyle = 'rgba(128,128,128,0.25)'
      for (let i = 1; i < FRAME_SIZE; i++) {
        ctx.fillRect(i * px, 0, 1, size)
        ctx.fillRect(0, i * px, size, 1)
      }
    }
  }, [frame, s, grid])

  return (
    <div
      ref={wrapRef}
      className={className}
      style={{ position: 'relative', width: cssSize, height: cssSize, flex: 'none', outline: '1px solid var(--line)' }}
    >
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={label}
        style={{ width: cssSize, height: cssSize, display: 'block', imageRendering: 'pixelated' }}
      />
      {overlay && <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>{overlay}</div>}
    </div>
  )
}
