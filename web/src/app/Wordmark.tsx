import { PALETTE } from '@/lib/palette'

// 7×5 pixel mark drawn from game palette cells (DESIGN.md §1).
const MARK = ['99.bb', '99.bb', '.....', 'ee.88', 'ee.88']
const MAP: Record<string, number> = { '9': 9, b: 11, e: 14, '8': 8 }

export function Wordmark() {
  const px = 3
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <svg width={5 * px} height={5 * px} viewBox="0 0 5 5" shapeRendering="crispEdges" aria-hidden>
        {MARK.flatMap((row, y) =>
          [...row].map((ch, x) =>
            ch === '.' ? null : <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={PALETTE[MAP[ch]]} />,
          ),
        )}
      </svg>
      <span className="mono" style={{ fontWeight: 500, letterSpacing: '0.04em' }}>
        GAME FACTORY
      </span>
    </span>
  )
}
