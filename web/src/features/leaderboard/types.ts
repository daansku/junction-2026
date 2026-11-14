export interface ModelCard {
  id: string
  display_name: string
  provider: string
  api_model?: string
  tier: 'frontier' | 'open' | 'finetuned' | 'baseline'
  input_modes?: string[]
  efforts?: string[]
  price_in?: number | null
  price_out?: number | null
  params?: string | null
  link?: string | null
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
  unique_games?: number
  attempts_per_game?: number
  single_attempt?: boolean
  levels_attempted: number
  levels_solved: number
  level_solve_rate: number
  game_win_rate: number
  score: number
  score_ci_low?: number | null
  score_ci_high?: number | null
  median_actions?: number | null
  tokens_in?: number | null
  tokens_out?: number | null
  cost_per_game?: number | null
  cost_per_solved_level?: number | null
  cost_underreported?: boolean
  cost_note?: string | null
  latency_ms_median?: number | null
  subset_note?: string | null
  model?: ModelCard | null
  display_name?: string
  provider?: string
  tier?: string
  input_modes?: string[] | null
  reasoning_mode?: string | null
  image_turns?: number | null
  max_tokens?: number | null
  best_run_id?: string | null
  model_order?: number
  resets_total?: number
  belief_accuracy?: number | null
  no_effect_rate?: number | null
  seen_score?: number | null
  unseen_pair_score?: number | null
  unseen_skin_score?: number | null
  probe_score?: number | null
  rhae_vs_human?: number | null
}

export interface LeaderboardDocument {
  generated_at: string
  harness_filter?: string | null
  rows: LeaderboardRow[]
}

export interface LeaderboardH2Document extends LeaderboardDocument {
  harness_version?: string
  h2_rules?: string[]
  h2_games_by_collection?: Record<string, string[]>
}

export interface BenchSuiteItem {
  id: string
  label: string
  group: 'primary' | 'negative_control' | 'bbh_logic_secondary' | string
  setting: string
  items?: number | null
}

export interface BenchMetricCell {
  tier: string
  n: number
  mean: number | null
  ci_low: number | null
  ci_high: number | null
  truncated: number
}

export interface BenchRunSummary {
  row_id: string
  raw_name: string
  model?: string | null
  lora?: string | null
  dev_slice: boolean
  config_hash?: string | null
  created_at?: string | null
  benchmarks: Record<string, BenchMetricCell>
  tier_means: Record<string, { benchmarks: number; mean: number }>
}

export interface BenchDeltaCell {
  tier: string
  n_shared: number
  n_only_ref: number
  n_only_cand: number
  delta: number | null
  ci_low: number | null
  ci_high: number | null
  excludes_zero: boolean
  mean_ref: number | null
  mean_cand: number | null
  truncated_ref?: number
  truncated_cand?: number
}

export interface BenchComparison {
  ref: string
  cand: string
  config_hash_match: boolean
  benchmarks: Record<string, BenchDeltaCell>
  tiers: Record<
    string,
    {
      benchmarks: number
      mean_delta: number | null
      sig_positive: number
      sig_negative: number
    }
  >
}

export interface BenchInDomainRow {
  role: string
  player_id: string
  display_name: string
  collection: string
  harness_version: string
  games: number
  levels_solved: number
  levels_attempted: number
  level_solve_rate: number
  score: number
  score_ci_low?: number | null
  score_ci_high?: number | null
  probe_score?: number | null
  no_effect_rate?: number | null
}

export interface BenchClaimEvaluation {
  status: 'transfer_supported' | 'null_transfer_in_domain_only' | 'pending_bench_runs' | string
  transfer_shown: boolean
  winning_candidate: string | null
  headline: string
  detail: string
}

export interface BenchSummaryDocument {
  generated_at: string
  protocol_version: string
  bootstrap_resamples: number
  bootstrap_seed: number
  suite_definition: BenchSuiteItem[]
  claim_evaluation: BenchClaimEvaluation
  in_domain_games: BenchInDomainRow[]
  runs: BenchRunSummary[]
  comparisons_vs_base: BenchComparison[]
  comparisons_vs_ctrl: BenchComparison[]
}

export interface DecisionPointsDocument {
  generated_at: string
  scope: string
  holdout_safety_note?: string
  total_decision_points: number
  train_safe_decision_points?: number
  failure_mode_counts: Record<string, number>
  oversampling_weights: {
    by_failure_mode: Record<string, number>
    by_rule: Record<string, number>
  }
}
