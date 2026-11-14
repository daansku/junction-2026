export interface InsightEvidence {
  label: string
  value: number | string
  run_id?: string | null
  step?: number | null
}

export interface InsightItem {
  id: string
  title: string
  summary: string
  category?: string
  severity?: string
  evidence: InsightEvidence[]
}

export interface InsightsDocument {
  generated_at: string
  insights: InsightItem[]
}

export interface RuleCell {
  rule: string
  player_id: string
  effort?: string | null
  intro_levels: number
  intro_solve_rate: number
  actions_to_first_use?: number | null
  wasted_actions?: number | null
  hypothesis_match_rate?: number | null
  repeated_no_effect_actions?: number | null
  belief_accuracy?: number | null
  intro_score?: number | null
  recombined_levels?: number
  recombined_solve_rate?: number | null
}

export interface LevelCurvePoint {
  level: number
  player_id: string
  tier: string
  attempts: number
  solve_rate: number
  mean_score: number
  mean_actions?: number | null
  mean_optimal?: number | null
}

export interface FailureExample {
  run_id?: string
  step?: number | null
  player_id?: string
  actions?: number
  level?: number
  rule?: string | null
  count?: number
}

export interface FailureModeEntry {
  mode: string
  count: number
  examples: FailureExample[]
}

export interface RulesDocument {
  generated_at: string
  rules?: string[]
  players?: string[]
  cells: RuleCell[]
  level_learning_curve?: LevelCurvePoint[]
  failure_modes?: FailureModeEntry[]
}
