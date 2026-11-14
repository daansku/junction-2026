export interface StageDisplayMeta {
  step: number
  title: string
  short: string
}

export const STAGE_META: Record<string, StageDisplayMeta> = {
  perception: {
    step: 1,
    title: 'Misread the board',
    short: 'Misread board',
  },
  rule_induction: {
    step: 2,
    title: 'Missed the new rule',
    short: 'Missed rule',
  },
  belief_updating: {
    step: 3,
    title: 'Stuck repeating moves',
    short: 'Stuck looping',
  },
  spatial_planning: {
    step: 4,
    title: 'Knew rule, bad plan',
    short: 'Bad plan',
  },
  budget_management: {
    step: 5,
    title: 'Reset too late',
    short: 'Late reset',
  },
}

export const CAUSE_LABELS: Record<string, string> = {
  coordinate_misread: 'Misread coordinates',
  unprobed_new_rule: 'Never tested rule',
  false_rule_hypothesis: 'Wrong rule guess',
  ignored_falsifying_feedback: 'Ignored blocked moves',
  knew_rule_failed_rollout: 'Knew rule, bad path',
  hazard_collision: 'Hit a hazard',
  sunk_cost_late_reset: 'Reset too late',
}

export const FAILURE_MODE_LABELS: Record<string, string> = {
  no_effect_loop: 'Wall-bump loops (no change)',
  zero_change_wall_bump: 'Wall-bump loops (no change)',
  belief_mismatch: 'Wrong board state belief',
  late_reset: 'Reset too late',
  budget_exhaustion: 'Ran out of moves',
  unsolved_level: 'Did not reach goal',
  rule_blindness: 'Never used new rule',
  missed_new_rule: 'Missed new rule',
  premature_hypothesis: 'Early wrong guess',
  hazard_death: 'Hit a hazard',
}

export const RULE_LABELS: Record<string, string> = {
  beacon_goal: 'Beacon Decoy',
  checkpoints: 'Checkpoints',
  collect_all: 'Collect All',
  conveyors: 'Conveyors',
  cracked_floor: 'Cracked Floor',
  enemies: 'Enemies',
  goal: 'Basic Goal',
  gravity: 'Gravity',
  hazards: 'Hazards',
  ice: 'Sliding Ice',
  keys_doors: 'Keys & Doors',
  no_reverse: 'No U-Turn',
  one_way: 'One-Way Tiles',
  phase_walls: 'Phase Walls',
  pits: 'Pits',
  plates_gates: 'Plates & Gates',
  push_blocks: 'Push Blocks',
  remap: 'Swapped Controls',
  rotation: 'Rotated Controls',
  stamina: 'Stamina',
  teleporters: 'Teleporters',
  twin: 'Twin Avatars',
}

const PLAYER_NAMES: Record<string, string> = {
  'verda-kimi-k3-1-pro': 'Kimi K3.1 Pro',
  'kimi-k3-1-pro': 'Kimi K3.1 Pro',
  'gemini-4-carbon': 'Gemini 4 Carbon',
  'gemini-4-argon': 'Gemini 4 Argon',
  'gemini-pro': 'Gemini 3.1 Pro',
  'gemini-flash': 'Gemini 3 Flash',
  'claude-sonnet-5-5': 'Claude Sonnet 5.5',
  'claude-haiku-5-5': 'Claude Haiku 5.5',
  'claude-opus-5-5': 'Claude Opus 5.5',
  'verda-nemotron-super-vl': 'Nemotron Super VL',
  'nemotron-3-5-super-vl': 'Nemotron Super VL',
  'nemotron-super-vl': 'Nemotron Super VL',
  'featherless-deepseek-v3-2': 'DeepSeek V3.2',
  'deepseek-v3-2': 'DeepSeek V3.2',
  'featherless-gpt-oss-120b': 'GPT-OSS 120B',
  'gpt-oss-120b': 'GPT-OSS 120B',
  'qwen3-5-9b': 'Qwen 3.5 9B',
  'qwen3-5-9b-ft-sft-v1': 'Qwen 3.5 9B (SFT v1)',
  human: 'Human',
  optimal: 'Optimal',
  random: 'Random',
  noop: 'Do Nothing',
  stop_early: 'Stop Early',
}

export function friendlyStageShort(stage?: string | null, fallback?: string | null): string {
  if (stage && STAGE_META[stage]) return STAGE_META[stage].short
  if (fallback) return fallback.replace(/_/g, ' ')
  return 'Failed'
}

export function friendlyStageTitle(stage?: string | null, fallback?: string | null): string {
  if (stage && STAGE_META[stage]) return `${STAGE_META[stage].step}. ${STAGE_META[stage].title}`
  if (fallback) return fallback.replace(/_/g, ' ')
  return 'Failed'
}

export function friendlyCause(cause?: string | null): string {
  if (!cause) return 'Failed level'
  return CAUSE_LABELS[cause] ?? cause.replace(/_/g, ' ')
}

export function friendlyFailureMode(mode: string): string {
  return FAILURE_MODE_LABELS[mode] ?? mode.replace(/_/g, ' ')
}

export function friendlyRule(rule?: string | null): string {
  if (!rule) return 'General'
  return RULE_LABELS[rule] ?? rule.replace(/_/g, ' ')
}

export function friendlyPlayer(raw?: string | null): string {
  if (!raw) return 'Model'
  const [base, effort] = raw.includes(':') ? raw.split(':', 2) : [raw, null]
  const clean = PLAYER_NAMES[base] ?? base.replace(/^(verda|featherless|modal)-/, '')
  return effort ? `${clean} (${effort})` : clean
}

/** Strip backticks & raw snake_case rule names from auditor text and cap to one crisp sentence. */
export function conciseSummary(raw?: string | null): string {
  if (!raw) return ''
  let s = raw.replace(/`([a-z0-9_]+)`/gi, (_, slug: string) => RULE_LABELS[slug] ?? slug.replace(/_/g, ' '))
  s = s.replace(/\bin h1 notes\b/gi, 'in notes').replace(/\bin h2 CoT\b/gi, 'in thinking')
  // Keep only the first sentence if multi-sentence
  const dotIdx = s.indexOf('. ')
  if (dotIdx > 25 && dotIdx < 165) {
    s = s.slice(0, dotIdx + 1)
  }
  return s.length > 165 ? `${s.slice(0, 162).trimEnd()}…` : s
}

export function truncateQuote(raw?: string | null, max = 115): string {
  if (!raw) return ''
  const clean = raw.replace(/\s+/g, ' ').trim()
  return clean.length > max ? `${clean.slice(0, max).trimEnd()}…` : clean
}
