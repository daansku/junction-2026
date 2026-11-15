// Mirrors contracts/ (contracts/ wins on any difference). Fields we do not
// rely on are typed loosely so additive contract changes never break the build.

/** 64 strings of 64 hex chars, row 0 at top. */
export type Frame = string[]

export type ActionName =
  | 'RESET'
  | 'ACTION1'
  | 'ACTION2'
  | 'ACTION3'
  | 'ACTION4'
  | 'ACTION5'
  | 'ACTION6'
  | 'ACTION7'

export type GameState = 'NOT_FINISHED' | 'WIN' | 'GAME_OVER'
export type RunOutcome = 'WIN' | 'GAME_OVER' | 'BUDGET' | 'ABORTED' | 'IN_PROGRESS'

export interface Truth {
  state: GameState
  level: number
  levels_total: number
  moves_used: number
  move_budget: number
  resets: number
  active_rules: string[]
  new_rule: string | null
  events: string[]
  optimal_moves: number
  [k: string]: unknown
}

export interface GameSpec {
  family?: string
  seed?: number
  n_levels?: number
  difficulty?: number
  rules?: string[] | null
  skin_shuffle?: boolean
}

export interface GameMeta {
  game_id: string
  collection?: string
  spec?: GameSpec
  engine_version?: string
  levels_total?: number
  difficulty?: number
  /** union of rules across levels */
  rules?: string[]
  rules_per_level?: string[][]
  optimal_moves_total?: number
  new_rules?: Array<string | null>
  optimal_moves?: number[]
  move_budgets?: number[]
  thumbnail_url?: string
  // legacy/mock convenience
  family?: string
  seed?: number
  n_levels?: number
  [k: string]: unknown
}

export interface LevelDescribe {
  level: number
  rules: string[]
  new_rule?: string | null
  move_budget: number
  optimal_moves: number
  optimal_path?: ActionName[]
  /** logical grid size; frame mapping mirrors engine/render/canvas.py */
  w?: number
  h?: number
  layout?: string
  start?: [number, number]
  goal?: [number, number]
  optimal_positions?: Array<[number, number]>
  [k: string]: unknown
}

export interface GameDescribe extends GameMeta {
  levels: LevelDescribe[]
  available_actions?: ActionName[]
}

export interface Player {
  kind: 'human' | 'model' | 'baseline'
  name: string
  model_id?: string
  provider?: string
  effort?: string
}

export interface SessionStart {
  session_id: string
  run_id: string
  frame: Frame
  available_actions: ActionName[]
}

export interface ActBody {
  action: ActionName
  x?: number
  y?: number
  reasoning?: string
  hypothesis?: string
  belief?: string
  usage?: { in?: number; out?: number; cost_usd?: number }
}

export interface ActResponse {
  frame: Frame
  available_actions: ActionName[]
}

export interface RunMeta {
  run_id: string
  run_key?: string
  game_id: string
  collection?: string
  split?: string
  player: Player
  harness_version?: string
  started_at?: string
  ended_at?: string | null
  outcome?: RunOutcome | null
  end_reason?: string | null
  levels_completed?: number
  levels_total?: number
  actions?: number
  resets?: number
  tokens_in?: number
  tokens_out?: number
  cost_usd?: number
  wall_s?: number
  [k: string]: unknown
}

export interface Step {
  i: number
  t_ms?: number
  /** null on step 0 (initial frame) */
  action: ActionName | null
  frame: Frame
  truth?: Partial<Truth>
  reasoning?: string
  hypothesis?: string
  belief?: string
  usage?: { in?: number; out?: number; cost_usd?: number }
  latency_ms?: number
  [k: string]: unknown
}

export interface RunsQuery {
  game_id?: string
  model_id?: string
  kind?: string
  collection?: string
}
