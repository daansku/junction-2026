export interface StageDisplayMeta {
  step: number
  title: string
  short: string
  hint: string
}

export const STAGE_META: Record<string, StageDisplayMeta> = {
  perception: {
    step: 1,
    title: 'Misread the Board',
    short: 'Misread Board',
    hint: 'Miscounted walls, player position, or goal coordinates',
  },
  rule_induction: {
    step: 2,
    title: 'Missed the New Rule',
    short: 'Missed Rule',
    hint: 'Never figured out what mechanic changed on this level',
  },
  belief_updating: {
    step: 3,
    title: 'Stuck Repeating Moves',
    short: 'Stuck Looping',
    hint: 'Kept repeating blocked moves that changed nothing on screen',
  },
  spatial_planning: {
    step: 4,
    title: 'Knew the Rule, Failed the Plan',
    short: 'Bad Plan',
    hint: 'Wrote the right rule in reasoning, then misplanned the path',
  },
  budget_management: {
    step: 5,
    title: 'Reset Too Late',
    short: 'Late Reset',
    hint: 'Waited until too few moves remained to finish after restarting',
  },
}

export const CAUSE_LABELS: Record<string, string> = {
  coordinate_misread: 'Misread board coordinates',
  unprobed_new_rule: 'Never tested the new rule',
  false_rule_hypothesis: 'Locked onto a wrong rule guess',
  ignored_falsifying_feedback: 'Ignored blocked moves (no change)',
  knew_rule_failed_rollout: 'Knew the rule, misplanned the path',
  hazard_collision: 'Walked into a hazard',
  sunk_cost_late_reset: 'Reset too late to finish in budget',
}

export const FAILURE_MODE_LABELS: Record<string, string> = {
  no_effect_loop: 'Repeating moves that change nothing (wall bumps)',
  zero_change_wall_bump: 'Repeating moves that change nothing (wall bumps)',
  belief_mismatch: 'Wrong belief about the board state',
  late_reset: 'Restarting too late to recover',
  budget_exhaustion: 'Running out of allowed moves',
  unsolved_level: 'Failing to reach the goal',
  rule_blindness: 'Never triggering the new rule',
  missed_new_rule: 'Missing the newly added rule',
  premature_hypothesis: 'Locking onto an early wrong guess',
  hazard_death: 'Stepping onto a hazard',
}

export const RULE_LABELS: Record<string, string> = {
  beacon_goal: 'Beacon Decoy',
  checkpoints: 'Checkpoints',
  collect_all: 'Collect All',
  conveyors: 'Conveyors',
  cracked_floor: 'Cracked Floor',
  enemies: 'Moving Enemies',
  goal: 'Basic Goal',
  gravity: 'Gravity Pull',
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
  stamina: 'Stamina Limit',
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
