// One colour per player, the same on every page (DESIGN.md §3 "assign by entity, not rank").
//
// Models get a fixed series slot. The slots below are chosen so that models shown together
// (same leaderboard collection, the challenge table, the overview) never share a colour.
// Models not listed fall back to their position in arena/models.yaml, so a new model still
// gets a stable colour without code changes. Humans and baselines are not series colours.
import { cssVar } from '@/lib/PlotFigure'

export const SERIES_SLOTS = 12

/** Base model id -> series slot (1-based, see --series-N in tokens.css). */
const MODEL_SLOT: Record<string, number> = {
  // eval-v2 / challenge regulars keep the colours they already had on the overview
  'gemini-4-carbon': 2,
  'gemini-4-argon': 3,
  'verda-kimi-k3-1-pro': 4,
  'gemini-flash': 5,
  'claude-sonnet-5-5': 6,
  'gemini-pro': 7,
  'claude-haiku-5-5': 8,
  'verda-deepseek-4-1-flash': 1,
  // eval-v1 / dev
  'claude-opus-5-5': 1,
  'gemini-4-hydrogen': 7,
  'nemotron-3-5-super-vl': 8,
  'modal-gemma-4-e4b': 9,
  'verda-ft-qwen3-5-9b': 10,
  'verda-base-qwen3-5-9b': 11,
  'featherless-gpt-oss-120b': 12,
  'featherless-open': 9,
}

const registryFiles = import.meta.glob('../../../arena/models.yaml', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

/** Model ids in arena/models.yaml order (fallback slot source). */
const REGISTRY_ORDER: string[] = (() => {
  const raw = Object.values(registryFiles)[0] ?? ''
  return Array.from(raw.matchAll(/^- id:\s*([\w.-]+)/gm), (m) => m[1])
})()

/** "gemini-flash@h2b" -> "gemini-flash" */
export function baseModelId(id: string): string {
  return id.split('@')[0]
}

function modelSlot(id: string): number {
  const base = baseModelId(id)
  const fixed = MODEL_SLOT[base]
  if (fixed) return fixed
  const order = REGISTRY_ORDER.indexOf(base)
  return order >= 0 ? (order % SERIES_SLOTS) + 1 : 1
}

export interface ColorSubject {
  kind?: string | null
  /** model id or leaderboard player_id */
  id?: string | null
}

/** Colour for a player: humans --text-1, baselines --text-3, models their fixed series slot. */
export function playerColor({ kind, id }: ColorSubject): string {
  if (kind === 'human' || id === 'human') return cssVar('--text-1') || '#efefec'
  if (kind === 'baseline' || id === 'optimal' || id === 'random' || id === 'noop' || id === 'stop_early')
    return cssVar('--text-3') || '#76756f'
  return cssVar(`--series-${modelSlot(id ?? '')}`) || cssVar('--accent') || '#ffdc00'
}
