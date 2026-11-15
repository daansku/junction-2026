import { modelName } from '@/lib/modelNames'
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
  // registry display names first, so Insights matches the leaderboard and challenge
  const clean = modelName(base) ?? PLAYER_NAMES[base] ?? base.replace(/^(verda|featherless|modal)-/, '')
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

// ---- Plain-language failure summaries
// The auditor writes one sentence per failure from fixed templates (analysis/src/analysis/explain.py), full of
// pipeline terms ("engine truth", "Knowing-Doing Gap", "spatial rollout", backticked slugs). These rules turn each
// template back into short, plain sentences with the same facts and numbers (style: github.com/blader/humanizer).
// Text that matches no template falls back to conciseSummary.

const EVENT_PLAIN: Record<string, string> = {
  bump: 'a wall',
  hurt: 'a hazard',
  caught: 'an enemy',
  'budget exhaustion': 'the move limit',
  floor_collapsed: 'a collapsing floor',
  walls_closed: 'a closing wall',
  pushed: 'a block it pushed',
  '[NO_EFFECT]': 'a wall',
}

function eventPlain(ev: string): string {
  return EVENT_PLAIN[ev] ?? RULE_LABELS[ev] ?? ev.replace(/_/g, ' ')
}

/** "ran into a wall at step 5", or "ran out of moves at step 150" for the move-limit event */
function hitAt(ev: string, step: string): string {
  return ev === 'budget exhaustion' ? `ran out of moves at step ${step}` : `ran into ${eventPlain(ev)} at step ${step}`
}

function rulePlain(rule: string): string {
  return RULE_LABELS[rule] ?? rule.replace(/_/g, ' ')
}

const T = '`([^`]+)`' // a backticked slug
const N = '(\\d+)'
const SRC = '(?:h\\d notes|h\\d CoT|hypothesis trace \\(CoT encrypted\\))'

const PLAIN_RULES: Array<[RegExp, (m: string[]) => string]> = [
  [
    new RegExp(`misread \\d+x\\d+ wall/goal coordinates around step ${N}.*?recorded ${N} blocked moves.*?optimal: ${N} moves`),
    (m) => `It misjudged where the walls and the goal were (from step ${m[1]}). ${m[2]} of its moves walked into a wall and changed nothing. The shortest route takes ${m[3]} moves.`,
  ],
  [
    new RegExp(`${SRC} correctly identified ${T} at step ${N}, but multi-step rollout failed across ${N} actions \\(engine optimal: ${N} moves\\)`),
    (m) => `It worked out ${rulePlain(m[1])} by step ${m[2]}, but couldn't turn that into a working route. It used ${m[3]} moves where ${m[4]} were enough.`,
  ],
  [
    new RegExp(`executed ${N} no-effect actions \\(streak of ${N} starting near step ${N}\\) without inducing ${T} or rerouting around engine ${T} feedback`),
    (m) =>
      `${m[1] === m[2] ? `It made ${m[1]} moves in a row that changed nothing, starting at step ${m[3]}.` : `It made ${m[1]} moves that changed nothing, ${m[2]} of them in a row from step ${m[3]}.`} It kept pushing into ${eventPlain(m[5])} instead of trying another way, and never figured out ${rulePlain(m[4])}.`,
  ],
  [
    new RegExp(`After triggering ${T} at step ${N}, model deduced ${T} in ${SRC} at step ${N} yet failed spatial recovery across ${N} moves \\(optimal: ${N} moves\\)`),
    (m) => `It ${hitAt(m[1], m[2])} and worked out ${rulePlain(m[3])} at step ${m[4]}, but never found a way through. It used ${m[5]} moves; the shortest route takes ${m[6]}.`,
  ],
  [
    new RegExp(`acted under an unverified hypothesis without deducing ${T} in ${SRC}; engine truth recorded ${T} at step ${N} \\(optimal: ${N} moves\\)`),
    (m) => `It went with an untested guess and never worked out ${rulePlain(m[1])}. It ${hitAt(m[2], m[3])}. The shortest route takes ${m[4]} moves.`,
  ],
  [
    new RegExp(`claimed forward movement at step ${N} while engine truth recorded ${T} \\(${T} / 0 pixels changed across ${N} consecutive steps\\)`),
    (m) => `At step ${m[1]} it thought it was moving forward, but it was stuck against ${eventPlain(m[3])} for ${m[4]} moves in a row.`,
  ],
  [
    new RegExp(`Despite mentioning ${T} at step ${N}, model repeated ${N} consecutive zero-effect actions without revising its blocked route`),
    (m) => `It mentioned ${rulePlain(m[1])} at step ${m[2]}, then made ${m[3]} moves in a row that changed nothing without changing its route.`,
  ],
  [
    new RegExp(`${SRC} never identified ${T}, and engine truth confirms ${N} ${T} events across all ${N} actions`),
    (m) =>
      m[2] === '0'
        ? `It never worked out ${rulePlain(m[1])} and never once used it in ${m[4]} moves.`
        : `It never worked out ${rulePlain(m[1])}, even though it ran into ${eventPlain(m[3])} ${m[2]} times in ${m[4]} moves.`,
  ],
  [
    new RegExp(`articulated ${T} in ${SRC} at step ${N}, yet its trajectory collided with ${T} at step ${N} \\(optimal: ${N} moves\\)`),
    (m) => `It described ${rulePlain(m[1])} at step ${m[2]}, but still ${hitAt(m[3], m[4])}. The shortest route takes ${m[5]} moves.`,
  ],
  [
    new RegExp(`deduced ${T} by step ${N} but delayed RESET until step ${N}, exhausting ${N}/${N} moves against a ${N}-move solution`),
    (m) => `It worked out ${rulePlain(m[1])} by step ${m[2]} but didn't restart the level until step ${m[3]}. By then it had used ${m[4]} of its ${m[5]} moves. The shortest route takes ${m[6]}.`,
  ],
  [
    new RegExp(`spent ${N} moves across ${N} late resets \\(first at step ${N}\\) without inducing ${T} in time for the ${N}-move path`),
    (m) => `It restarted the level ${m[2]} times (first at step ${m[3]}) and used ${m[1]} moves, but never worked out ${rulePlain(m[4])}. The shortest route takes ${m[5]} moves.`,
  ],
  [
    new RegExp(`reported \`belief=(\\w+)\` at step ${N} while engine truth was \`(\\w+)\` \\(${T} remained unsatisfied\\)`),
    (m) => `At step ${m[2]} it thought it had ${m[1] === 'won' ? 'won' : m[1]}, but the level was still going: ${rulePlain(m[4])} wasn't done yet.`,
  ],
]

/** One or two plain sentences for a failure card, built from the auditor's sentence. */
export function plainSummary(raw?: string | null): string {
  if (!raw) return ''
  for (const [rx, fmt] of PLAIN_RULES) {
    const m = raw.match(rx)
    if (m) return fmt(m)
  }
  return conciseSummary(raw)
}

export function truncateQuote(raw?: string | null, max = 115): string {
  if (!raw) return ''
  const clean = raw.replace(/\s+/g, ' ').trim()
  return clean.length > max ? `${clean.slice(0, max).trimEnd()}…` : clean
}
