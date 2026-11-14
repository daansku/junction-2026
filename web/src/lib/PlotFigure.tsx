import * as Plot from '@observablehq/plot'
import { useEffect, useRef, useState } from 'react'

/** Read a CSS custom property (theme-aware chart colours). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** Categorical series colours in fixed order (DESIGN.md §3). Assign by entity, never by rank. */
export function seriesColors(): string[] {
  return [1, 2, 3, 4, 5, 6, 7, 8].map((i) => cssVar(`--series-${i}`))
}

/** Plot defaults matching DESIGN.md §7. Spread into Plot.plot options. */
export function plotDefaults(): Partial<Plot.PlotOptions> {
  return {
    style: {
      background: 'transparent',
      color: cssVar('--text-3'),
      fontFamily: cssVar('--font-mono'),
      fontSize: '11px',
      overflow: 'visible',
    },
    marginLeft: 48,
    grid: true,
  }
}

/**
 * Wraps Observable Plot for React. Pass a function so the figure re-renders on
 * resize and theme change with fresh token values.
 */
export function PlotFigure({
  make,
  deps = [],
  className,
}: {
  make: (width: number) => Plot.PlotOptions
  deps?: unknown[]
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(Math.max(240, Math.floor(el.clientWidth))))
    ro.observe(el)
    return () => {
      ro.disconnect()
    }
  }, [])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const fig = Plot.plot({ ...plotDefaults(), width, ...make(width) })
    el.replaceChildren(fig)
    return () => fig.remove()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, ...deps])

  return <div ref={ref} className={className} style={{ width: '100%' }} />
}
