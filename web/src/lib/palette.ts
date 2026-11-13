// Game palette, 16 colours, index 0–15. Source of truth: contracts/palette.json (A2).
// Until that file exists we fall back to a built-in copy of the ARC-AGI-3 palette.

const FALLBACK: string[] = [
  '#FFFFFF', '#CCCCCC', '#999999', '#666666',
  '#333333', '#000000', '#E53AA3', '#FF7BCC',
  '#F93C31', '#1E93FF', '#88D8F1', '#FFDC00',
  '#FF851B', '#921231', '#4FCC30', '#A356D6',
]

const contractFiles = import.meta.glob('../../../contracts/palette*.json', {
  eager: true,
  import: 'default',
}) as Record<string, unknown>

function normHex(v: unknown): string | null {
  if (typeof v !== 'string') return null
  const s = v.trim()
  if (/^#?[0-9a-fA-F]{6}$/.test(s)) return s.startsWith('#') ? s : `#${s}`
  return null
}

/** Accepts ["#hex", …], {colors:[…]}, {"0":"#hex",…} or [{index,hex}, …]. */
export function parsePalette(raw: unknown): string[] | null {
  let list: unknown = raw
  if (list && typeof list === 'object' && !Array.isArray(list)) {
    const o = list as Record<string, unknown>
    list = o.colors ?? o.palette ?? o.hex ?? Object.keys(o).sort((a, b) => +a - +b).map((k) => o[k])
  }
  if (!Array.isArray(list)) return null
  const out: string[] = []
  for (const item of list) {
    if (typeof item === 'string') out.push(normHex(item) ?? '')
    else if (item && typeof item === 'object') {
      const it = item as Record<string, unknown>
      const idx = typeof it.index === 'number' ? it.index : out.length
      out[idx] = normHex(it.hex ?? it.color ?? it.value) ?? ''
    }
  }
  if (out.length < 16 || out.slice(0, 16).some((c) => !c)) return null
  return out.slice(0, 16)
}

const fromContract = Object.values(contractFiles)[0]
export const PALETTE: string[] = parsePalette(fromContract) ?? FALLBACK
export const PALETTE_SOURCE: 'contract' | 'fallback' = parsePalette(fromContract) ? 'contract' : 'fallback'

/** Palette as packed RGBA for fast canvas drawing. */
export const PALETTE_RGB: Array<[number, number, number]> = PALETTE.map((h) => {
  const n = parseInt(h.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
})
