// Game palette, 16 colours, index 0–15. Source of truth: contracts/palette.json.
// Fallback is a copy of contracts/palette.json v1, used only if the file is missing.

const FALLBACK: string[] = [
  '#000000', '#1E5BD8', '#E5383B', '#2FB54A',
  '#F5C518', '#8A8F98', '#D63AAF', '#F2832B',
  '#6FD3F2', '#7A1F2B', '#FFFFFF', '#3A3F47',
  '#8E5CE6', '#1FA39A', '#A8D94A', '#8B5A2B',
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
