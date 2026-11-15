// One display name per model, the same on every page. Source: `display_name` in arena/models.yaml
// (the registry the leaderboard is built from). Short ids that analysis files use without the
// provider prefix ("ft-qwen3-5-9b", "open", "gemma-4-e4b") resolve to the same entry.

const registryFiles = import.meta.glob('../../../arena/models.yaml', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

/** model id -> display_name from arena/models.yaml */
const REGISTRY: Map<string, string> = (() => {
  const raw = Object.values(registryFiles)[0] ?? ''
  const out = new Map<string, string>()
  for (const block of raw.split(/^- id:/m).slice(1)) {
    const id = block.match(/^\s*([\w.-]+)/)?.[1]
    const name = block.match(/^\s*display_name:\s*(.+?)\s*$/m)?.[1]?.replace(/^["']|["']$/g, '')
    if (id && name) out.set(id, name)
  }
  return out
})()

const PROVIDER_PREFIXES = ['', 'verda-', 'featherless-', 'modal-']

/** Ids used by analysis/insights files that are not a registry id with a provider prefix. */
const ALIASES: Record<string, string> = {
  'ft-qwen3-5-9b': 'verda-ft-qwen3-5-9b',
  'base-qwen3-5-9b': 'verda-base-qwen3-5-9b',
  'deepseek-v3-2': 'featherless-open',
  'nemotron-super-vl': 'nemotron-3-5-super-vl',
  'verda-nemotron-super-vl': 'nemotron-3-5-super-vl',
}

const NON_MODELS: Record<string, string> = {
  human: 'Human',
  optimal: 'Optimal',
  random: 'Random',
  noop: 'Do nothing',
  stop_early: 'Stop early',
}

/** Display name for a model or player id ("gemini-flash@h2b" and "open" included), or null if unknown. */
export function modelName(rawId?: string | null): string | null {
  if (!rawId) return null
  const id = rawId.split('@')[0]
  if (NON_MODELS[id]) return NON_MODELS[id]
  const target = ALIASES[id] ?? id
  for (const p of PROVIDER_PREFIXES) {
    const hit = REGISTRY.get(p + target)
    if (hit) return hit
  }
  return null
}
