import type { LeaderboardRow } from './types'

/**
 * Board ranking:
 * completion first. Rank by games won, then levels solved, then efficiency (the `score` field:
 * mean over levels of min(1, optimal / moves) if solved, else 0) as the tiebreak.
 * The Harbor / RL reward is unchanged; only the order on the boards changes.
 */
export function completionCompare(a: LeaderboardRow, b: LeaderboardRow): number {
  return (
    (b.game_win_rate ?? 0) - (a.game_win_rate ?? 0) ||
    (b.level_solve_rate ?? 0) - (a.level_solve_rate ?? 0) ||
    (b.score ?? 0) - (a.score ?? 0)
  )
}

/** The row that ranks first under completionCompare, or null. */
export function bestByCompletion(rows: LeaderboardRow[]): LeaderboardRow | null {
  return rows.reduce<LeaderboardRow | null>((acc, cur) => (!acc || completionCompare(cur, acc) < 0 ? cur : acc), null)
}
