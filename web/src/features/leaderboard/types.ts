export interface ModelCard {
  id: string
  display_name: string
  provider: string
  tier: 'frontier' | 'open' | 'finetuned' | 'baseline'
  release_date?: string | null
  knowledge_cutoff?: string | null
  params_b?: number | null
  context_window?: number | null
  supports_reasoning?: boolean
  default_effort?: string | null
  pricing_per_mtok?: {
    in: number
    out: number
  } | null
  notes?: string | null
}

export interface LeaderboardRow {
  player_id: string
  kind: 'model' | 'baseline' | 'human'
  effort?: string | null
  collection: string
  harness_version?: string | null
  games: number
  levels_attempted: number
  levels_solved: number
  level_solve_rate: number
  game_win_rate: number
  score: number
  median_actions?: number | null
  tokens_in?: number | null
  tokens_out?: number | null
  cost_per_game?: number | null
  cost_per_solved_level?: number | null
  latency_ms_median?: number | null
  subset_note?: string | null
  model?: ModelCard | null
  display_name?: string
  provider?: string
  tier?: string
  model_order?: number
  resets_total?: number
  belief_accuracy?: number | null
  no_effect_rate?: number | null
  rhae_vs_human?: number | null
}

export interface LeaderboardDocument {
  generated_at: string
  rows: LeaderboardRow[]
}
