import { api } from '@/lib/api'
import type {
  BenchSuiteItem,
  BenchSummaryDocument,
  DecisionPointsDocument,
  LeaderboardH2Document,
} from './types'

export const DEFAULT_H2_RULES: string[] = [
  'Multi-turn conversation: model sees its own full prior turn history (never stateless notes-only).',
  'Reasoning retained across turns: Anthropic thinking blocks preserved; OpenAI-compat assistant message returned verbatim.',
  'Native tool calling: structured act(action, hypothesis, belief) tool; invalid calls cost a turn, not an action.',
  'Leaderboard-standard effort: high / max per model, explicitly labelled per row and never silently mixed.',
  'Generous output cap: 64k tokens (Anthropic streamed) / 32k tokens (OpenAI-compatible) so thinking never truncates.',
  'Provider-default sampling: no artificial temperature overrides on reasoning models.',
  'Fixed context window: full text history + last 5 image frames (older frames cleared) + prompt caching enabled.',
  'Uncertainty reported: 95% bootstrap CI over game scores; single-attempt rows explicitly badged.',
  'Zero truth leakage: pixels + RLE only under prompts/system_h2.md; hidden rules never enter prompts.',
]

export const DEFAULT_BENCH_SUITE: BenchSuiteItem[] = [
  { id: 'bbh', label: 'BIG-Bench Hard (27 tasks)', group: 'primary', setting: '3-shot CoT', items: 1350 },
  { id: 'math', label: 'MATH', group: 'primary', setting: '0-shot CoT', items: 350 },
  { id: 'gsm8k', label: 'GSM8K', group: 'primary', setting: '8-shot CoT', items: 250 },
  { id: 'medqa', label: 'MedQA-USMLE (4-opt)', group: 'primary', setting: '0-shot', items: 1273 },
  { id: 'mmlu_pro_health', label: 'MMLU-Pro: Health', group: 'primary', setting: '5-shot CoT', items: 100 },
  { id: 'mmlu_pro_law', label: 'MMLU-Pro: Law', group: 'primary', setting: '5-shot CoT', items: 100 },
  { id: 'mmlu_pro_history', label: 'MMLU-Pro: History (Negative Ctrl)', group: 'negative_control', setting: '5-shot CoT', items: 100 },
  { id: 'bbh_tracking_shuffled_objects', label: 'BBH: Tracking Shuffled Objects', group: 'bbh_logic_secondary', setting: '3-shot CoT', items: 50 },
  { id: 'bbh_navigate', label: 'BBH: Navigate', group: 'bbh_logic_secondary', setting: '3-shot CoT', items: 50 },
  { id: 'bbh_logical_deduction', label: 'BBH: Logical Deduction', group: 'bbh_logic_secondary', setting: '3-shot CoT', items: 50 },
  { id: 'bbh_web_of_lies', label: 'BBH: Web of Lies', group: 'bbh_logic_secondary', setting: '3-shot CoT', items: 50 },
  { id: 'bbh_temporal_sequences', label: 'BBH: Temporal Sequences', group: 'bbh_logic_secondary', setting: '3-shot CoT', items: 50 },
]

export async function fetchLeaderboardH2(): Promise<LeaderboardH2Document> {
  try {
    const doc = await api.derived<LeaderboardH2Document>('leaderboard_h2')
    if (doc && Array.isArray(doc.rows)) {
      return {
        ...doc,
        h2_rules: doc.h2_rules?.length ? doc.h2_rules : DEFAULT_H2_RULES,
      }
    }
  } catch {
    /* graceful fallback in mock mode or before server rebuild */
  }
  return {
    generated_at: '',
    harness_version: 'h2',
    h2_rules: DEFAULT_H2_RULES,
    h2_games_by_collection: {},
    rows: [],
  }
}

export async function fetchBenchSummary(): Promise<BenchSummaryDocument> {
  try {
    const doc = await api.derived<BenchSummaryDocument>('bench_summary')
    if (doc && doc.claim_evaluation) {
      return {
        ...doc,
        suite_definition: doc.suite_definition?.length ? doc.suite_definition : DEFAULT_BENCH_SUITE,
      }
    }
  } catch {
    /* graceful fallback in mock mode or before server rebuild */
  }
  return {
    generated_at: '',
    protocol_version: 'ft-benchmarks-v3',
    bootstrap_resamples: 10000,
    bootstrap_seed: 20261114,
    suite_definition: DEFAULT_BENCH_SUITE,
    claim_evaluation: {
      status: 'pending_bench_runs',
      transfer_shown: false,
      winning_candidate: null,
      headline: 'Pre-registered benchmark protocol locked; outside-benchmark GPU runs in flight.',
      detail: 'Awaiting /api/derived/bench_summary.json snapshot or mock data.',
    },
    in_domain_games: [],
    runs: [],
    comparisons_vs_base: [],
    comparisons_vs_ctrl: [],
  }
}

export async function fetchDecisionPoints(): Promise<DecisionPointsDocument> {
  try {
    const doc = await api.derived<DecisionPointsDocument>('decision_points')
    if (doc && doc.oversampling_weights) return doc
  } catch {
    /* graceful fallback in mock mode or before server rebuild */
  }
  return {
    generated_at: '',
    scope: 'dev_only_holdout_safe',
    total_decision_points: 0,
    failure_mode_counts: {},
    oversampling_weights: {
      by_failure_mode: {},
      by_rule: {},
    },
  }
}
