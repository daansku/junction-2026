import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Chip, Empty, Loading, Panel, Stat, Swatch, cx } from '@/design/primitives'
import { cssVar, seriesColors } from '@/lib/PlotFigure'
import { ModelCardDialog, cardLabel } from './ModelCardDialog'
import type {
  BenchComparison,
  BenchDeltaCell,
  BenchSummaryDocument,
  DecisionPointsDocument,
  LeaderboardH2Document,
  LeaderboardRow,
} from './types'

function fmtFloat(v: number | null | undefined, digits = 3): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function fmtSigned(v: number | null | undefined, digits = 3): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}`
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  if (v === 0) return '$0.00'
  if (v < 0.01) return '<$0.01'
  return `$${v.toFixed(2)}`
}

function seriesColorFor(row: LeaderboardRow, fallbackIdx: number): string {
  if (row.kind === 'baseline') return cssVar('--text-3') || '#76756f'
  if (row.kind === 'human') return cssVar('--text-1') || '#f3f2ee'
  const palette = seriesColors()
  const idx =
    row.model_order != null && row.model_order < 900
      ? Math.abs(row.model_order) % palette.length
      : fallbackIdx % palette.length
  return palette[idx] || cssVar('--accent')
}

function rowLabel(r: LeaderboardRow): string {
  const base = r.display_name || r.model?.display_name || r.player_id
  return r.effort ? `${base} (${r.effort})` : base
}

function formatReasoningMode(mode?: string | null): string {
  if (!mode) return '—'
  if (mode.includes('anthropic')) return 'thinking blocks preserved'
  if (mode.includes('verbatim')) return 'assistant turn verbatim'
  return mode
}

type H2SortKey = 'score' | 'level_solve_rate' | 'game_win_rate' | 'median_actions' | 'cost_per_game'
type H2KindFilter = 'all' | 'model' | 'baseline' | 'human'

const H2_HIGHER_IS_BETTER = new Set<H2SortKey>(['score', 'level_solve_rate', 'game_win_rate'])
const H2_DEFAULT_COLLECTION = 'eval-v2'

/** "Evaluated on 1/6 games in eval-v1 · …" -> "1/6" */
function subsetCoverage(note: string | null | undefined): string | null {
  const m = note?.match(/(\d+\/\d+)\s+games/)
  return m ? m[1] : null
}

export function LeaderboardH2View(props: {
  doc?: LeaderboardH2Document
  isLoading?: boolean
  resolveRunFallback: (row: LeaderboardRow) => string | null
}) {
  const { doc, isLoading, resolveRunFallback } = props
  const [collectionPick, setCollection] = useState<string | null>(null)
  const [kindFilter, setKindFilter] = useState<H2KindFilter>('all')
  const [sortKey, setSortKey] = useState<H2SortKey>('score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [cardRow, setCardRow] = useState<LeaderboardRow | null>(null)

  const allRows = doc?.rows ?? []
  const collections = useMemo(() => {
    const s = new Set<string>()
    for (const r of allRows) s.add(r.collection || 'eval-v1')
    return ['all', ...Array.from(s).sort()]
  }, [allRows])
  const collection =
    collectionPick ?? (collections.includes(H2_DEFAULT_COLLECTION) ? H2_DEFAULT_COLLECTION : 'all')

  const collectionRows = useMemo(
    () => (collection === 'all' ? allRows : allRows.filter((r) => r.collection === collection)),
    [allRows, collection],
  )

  const sortedRows = useMemo(() => {
    const rows = kindFilter === 'all' ? collectionRows : collectionRows.filter((r) => r.kind === kindFilter)
    return [...rows].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      const cmp = Number(av) - Number(bv)
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [collectionRows, kindFilter, sortKey, sortDir])

  const bestValues = useMemo(() => {
    const out: Partial<Record<H2SortKey, number>> = {}
    for (const k of ['score', 'level_solve_rate', 'game_win_rate', 'median_actions', 'cost_per_game'] as H2SortKey[]) {
      const vals = sortedRows.map((r) => r[k]).filter((v): v is number => typeof v === 'number' && !Number.isNaN(v))
      if (vals.length) out[k] = H2_HIGHER_IS_BETTER.has(k) ? Math.max(...vals) : Math.min(...vals)
    }
    return out
  }, [sortedRows])

  const isBest = (row: LeaderboardRow, key: H2SortKey) => {
    const v = row[key]
    const best = bestValues[key]
    return typeof v === 'number' && best != null && Math.abs(v - best) < 1e-6
  }

  const handleSort = (key: H2SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else {
      setSortKey(key)
      setSortDir(H2_HIGHER_IS_BETTER.has(key) ? 'desc' : 'asc')
    }
  }

  const sortTh = (key: H2SortKey, label: string) => (
    <th className="num">
      <button className={cx('lb-sort-btn', sortKey === key && 'active')} onClick={() => handleSort(key)}>
        {label}
        {sortKey === key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
      </button>
    </th>
  )

  const label = (r: LeaderboardRow) => (collection === 'all' ? rowLabel(r) : cardLabel(r))

  const kpi = useMemo(() => {
    const models = collectionRows.filter((r) => r.kind === 'model')
    const pickBest = (rows: LeaderboardRow[]) =>
      rows.reduce<LeaderboardRow | null>((acc, cur) => (!acc || cur.score > acc.score ? cur : acc), null)
    // Prefer rows evaluated on more than one game so a lucky single game doesn't headline.
    const best = pickBest(models.filter((r) => r.games >= 2)) ?? pickBest(models)
    const human = collectionRows.find((r) => r.kind === 'human')
    const optimal = collectionRows.find((r) => r.player_id === 'optimal')
    const totalGames = models.reduce((acc, r) => acc + (r.games || 0), 0)
    return { modelsCount: models.length, best, human, optimal, totalGames }
  }, [collectionRows])

  if (isLoading && !doc) {
    return <Loading what="Loading h2 leaderboard" />
  }

  if (allRows.length === 0) {
    return <Empty>No h2 runs published yet.</Empty>
  }

  return (
    <>
      <div className="lb-kpi-grid">
        <div className="lb-kpi-cell">
          <Stat
            label="Best Model"
            value={kpi.best ? fmtFloat(kpi.best.score, 3) : '—'}
            sub={kpi.best ? label(kpi.best) : undefined}
          />
        </div>
        <div className="lb-kpi-cell">
          <Stat
            label="Human"
            value={fmtFloat(kpi.human?.score, 3)}
            sub={`optimal ${fmtFloat(kpi.optimal?.score ?? 1, 3)}`}
          />
        </div>
        <div className="lb-kpi-cell">
          <Stat label="Games Evaluated" value={kpi.totalGames} sub={`${kpi.modelsCount} models`} />
        </div>
      </div>

      <div className="lb-controls">
        <div className="lb-filter-group" role="group" aria-label="Filter h2 collection">
          <span className="kicker lb-filter-label">Collection</span>
          {collections.map((c) => (
            <Button key={c} mono active={collection === c} onClick={() => setCollection(c)}>
              {c}
            </Button>
          ))}
        </div>
        <div className="lb-filter-group">
          <span className="kicker lb-filter-label">Player</span>
          {(['all', 'model', 'baseline', 'human'] as H2KindFilter[]).map((k) => (
            <Button key={k} mono active={kindFilter === k} onClick={() => setKindFilter(k)}>
              {k}
            </Button>
          ))}
        </div>
      </div>

      <Panel label="Leaderboard" actions={<span className="mono muted">click a name for its model card</span>}>
        <div className="table-wrap">
          <table className="table lb-ledger-table">
            <thead>
              <tr>
                <th>Player</th>
                <th className="num">Games</th>
                {sortTh('score', 'Score')}
                {sortTh('level_solve_rate', 'Levels Solved')}
                {sortTh('game_win_rate', 'Games Won')}
                {sortTh('median_actions', 'Med. Actions')}
                {sortTh('cost_per_game', 'Cost / Game')}
                <th className="num">Replay</th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row, idx) => {
                const color = seriesColorFor(row, idx)
                const runId = row.best_run_id ?? resolveRunFallback(row)
                const coverage = subsetCoverage(row.subset_note)
                const showCi = row.score_ci_low != null && row.score_ci_high != null && row.games > 1
                return (
                  <tr key={`${row.player_id}-${row.collection}-${row.effort ?? 'none'}`}>
                    <td>
                      <button type="button" className="lb-name-btn" onClick={() => setCardRow(row)}>
                        <Swatch color={color} />
                        <span>{label(row)}</span>
                        {row.kind !== 'model' && <span className="lb-tag">{row.kind}</span>}
                      </button>
                    </td>
                    <td className="num" title={row.subset_note ?? undefined}>
                      {coverage ?? row.games}
                      {coverage && <span className="lb-tag lb-tag-warn lb-tag-inline">subset</span>}
                    </td>
                    <td
                      className={cx('num', 'lb-score-td', isBest(row, 'score') && 'lb-best')}
                      title={showCi ? `95% CI ${fmtFloat(row.score_ci_low, 3)} – ${fmtFloat(row.score_ci_high, 3)}` : undefined}
                    >
                      <div className="lb-score-wrap">
                        <span>{fmtFloat(row.score, 3)}</span>
                        <div className="lb-score-track" aria-hidden="true">
                          <div
                            className="lb-score-fill"
                            style={{
                              width: `${Math.max(0, Math.min(100, row.score * 100))}%`,
                              background: color,
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className={cx('num', isBest(row, 'level_solve_rate') && 'lb-best')}>
                      {fmtPct(row.level_solve_rate)}
                    </td>
                    <td className={cx('num', isBest(row, 'game_win_rate') && 'lb-best')}>
                      {fmtPct(row.game_win_rate)}
                    </td>
                    <td className={cx('num', isBest(row, 'median_actions') && 'lb-best')}>
                      {row.median_actions != null ? Math.round(row.median_actions) : '—'}
                    </td>
                    <td className={cx('num', isBest(row, 'cost_per_game') && 'lb-best')}>
                      {row.cost_per_game != null ? (
                        fmtUsd(row.cost_per_game)
                      ) : row.kind === 'model' ? (
                        <span className="muted" title="Run on sponsored GPU credits">credits</span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="num mono">
                      {runId ? (
                        <Link to={`/replay/${encodeURIComponent(runId)}`} className="lb-replay-pill">
                          ▶
                        </Link>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      {cardRow && (
        <ModelCardDialog
          row={cardRow}
          color={seriesColorFor(cardRow, sortedRows.indexOf(cardRow))}
          extra={[
            [
              '95% CI',
              cardRow.score_ci_low != null && cardRow.score_ci_high != null && cardRow.games > 1
                ? `${fmtFloat(cardRow.score_ci_low, 3)} – ${fmtFloat(cardRow.score_ci_high, 3)}`
                : null,
            ],
            ['Attempts / game', cardRow.kind === 'model' ? `k=${cardRow.attempts_per_game ?? 1}` : null],
            ['Reasoning', cardRow.reasoning_mode ? formatReasoningMode(cardRow.reasoning_mode) : null],
            ['Output cap', cardRow.max_tokens ? `${Math.round(cardRow.max_tokens / 1000)}k tokens` : null],
            ['Image history', cardRow.image_turns ? `last ${cardRow.image_turns} frames` : null],
          ]}
          onClose={() => setCardRow(null)}
        />
      )}
    </>
  )
}

const GROUP_LABEL: Record<string, string> = {
  primary: 'PRIMARY FAR-TRANSFER HEADLINE (6)',
  negative_control: 'NEGATIVE CONTROL (FORMAT GUARD)',
  bbh_logic_secondary: 'PRE-DECLARED BBH LOGIC SUBSET (5)',
}

function findComp(list: BenchComparison[], cand: string): BenchComparison | undefined {
  return list.find((c) => c.cand === cand)
}

export function PostTrainingBenchView(props: {
  bench?: BenchSummaryDocument
  decisionPoints?: DecisionPointsDocument
  isLoading?: boolean
}) {
  const { bench, decisionPoints, isLoading } = props
  const [selectedCand, setSelectedCand] = useState<string>('auto')
  const [showCheckpoints, setShowCheckpoints] = useState<boolean>(false)

  const runs = bench?.runs ?? []
  const hasCheckpoints = useMemo(() => runs.some((r) => r.is_checkpoint), [runs])
  const candidates = useMemo(
    () =>
      runs.filter(
        (r) =>
          (showCheckpoints || !r.is_checkpoint) &&
          !['base', 'base-dev', 'ctrl', 'think-ctrl'].includes(r.row_id),
      ),
    [runs, showCheckpoints],
  )

  const activeCand = useMemo(() => {
    if (selectedCand !== 'auto' && candidates.some((c) => c.row_id === selectedCand)) {
      return selectedCand
    }
    if (
      bench?.claim_evaluation.winning_candidate &&
      candidates.some((c) => c.row_id === bench.claim_evaluation.winning_candidate)
    ) {
      return bench.claim_evaluation.winning_candidate
    }
    return (
      candidates.find((c) => c.row_id === 'think-gridbranch')?.row_id ??
      candidates.find((c) => c.row_id === 'think-games')?.row_id ??
      candidates.find((c) => c.row_id === 'finalist')?.row_id ??
      candidates.find((c) => c.row_id === 'mix')?.row_id ??
      candidates.find((c) => c.row_id === 'games')?.row_id ??
      candidates.find((c) => c.row_id === 'rl-nothink')?.row_id ??
      candidates[0]?.row_id ??
      'think-gridbranch'
    )
  }, [selectedCand, candidates, bench])

  if (isLoading && !bench) {
    return <Loading what="Loading post-training & benchmark transfer summary" />
  }

  const claim = bench?.claim_evaluation
  const baseRun =
    runs.find((r) => r.row_id === 'base' && !r.dev_slice) ??
    runs.find((r) => r.row_id === 'base') ??
    runs.find((r) => r.row_id === 'base-dev')
  const candRun = runs.find((r) => r.row_id === activeCand)
  const vsCtrl = findComp(bench?.comparisons_vs_ctrl ?? [], activeCand)
  const vsBase = findComp(bench?.comparisons_vs_base ?? [], activeCand)
  const rawLower = (candRun?.raw_name ?? '').toLowerCase()
  const isThinkCand =
    activeCand === 'think-games' ||
    activeCand === 'think-gridbranch' ||
    rawLower.startsWith('think-games-') ||
    rawLower.startsWith('rl-think-games-') ||
    rawLower.startsWith('think-gridbranch-') ||
    rawLower.startsWith('rl-think-gridbranch-')
  const ctrlRun =
    (vsCtrl ? runs.find((r) => r.row_id === vsCtrl.ref) : undefined) ??
    (isThinkCand
      ? runs.find((r) => r.row_id === 'think-ctrl') ?? runs.find((r) => r.row_id === 'ctrl')
      : runs.find((r) => r.row_id === 'ctrl') ?? runs.find((r) => r.row_id === 'think-ctrl'))

  const claimChipOutcome =
    claim?.status === 'transfer_supported'
      ? 'WIN'
      : claim?.status === 'null_transfer_in_domain_only'
        ? 'BUDGET'
        : 'IN_PROGRESS'

  const claimChipLabel =
    claim?.status === 'transfer_supported'
      ? 'TRANSFER SUPPORTED'
      : claim?.status === 'null_transfer_in_domain_only'
        ? 'HONEST NULL / IN-DOMAIN'
        : 'BENCH IN FLIGHT'

  const modeWeights = Object.entries(decisionPoints?.oversampling_weights?.by_failure_mode ?? {})
  const ruleWeights = Object.entries(decisionPoints?.oversampling_weights?.by_rule ?? {}).slice(0, 8)

  return (
    <div className="lb-stack">
      <Panel
        label="Pre-Registered Honesty Claim Rule (PLAN §3.3 · bench/PROTOCOL.md §6)"
        actions={
          <span className="mono muted">
            {bench?.bootstrap_resamples?.toLocaleString() ?? '10,000'} paired bootstrap resamples · seed{' '}
            {bench?.bootstrap_seed ?? 20261114}
          </span>
        }
      >
        <div className="lb-claim-banner">
          <div className="lb-claim-head">
            <Chip outcome={claimChipOutcome}>{claimChipLabel}</Chip>
            <strong>{claim?.headline ?? 'Pre-registered protocol active.'}</strong>
          </div>
          <p className="lb-claim-detail">{claim?.detail}</p>
          <div className="lb-claim-gates mono">
            <span>Gate 1: cand &gt; equal-token ctrl on 6-task Primary Headline</span>
            <span>Gate 2: ≥ 2 Primary benchmarks with paired 95% CI excluding 0</span>
            <span>Gate 3: MMLU-Pro History (negative ctrl) Δ &lt; Primary Headline Δ</span>
          </div>
        </div>
      </Panel>

      <Panel
        label="Step 0 & In-Domain Game Evaluation (Qwen3.5-9B on Held-Out Worlds)"
        actions={<span className="mono muted">disjoint seeds from train-v1 · zero holdout leakage</span>}
      >
        {(bench?.in_domain_games?.length ?? 0) === 0 ? (
          <Empty>No Qwen3.5-9B game benchmark rows recorded in this snapshot yet.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Model</th>
                  <th>Collection</th>
                  <th>Harness</th>
                  <th className="num">Games</th>
                  <th className="num">Levels Solved</th>
                  <th className="num">Solve Rate</th>
                  <th className="num">Score [95% CI]</th>
                  <th className="num">No-Effect Loop</th>
                </tr>
              </thead>
              <tbody>
                {(bench?.in_domain_games ?? []).map((r, idx) => (
                  <tr key={`${r.player_id}-${r.collection}-${r.harness_version}-${idx}`}>
                    <td className="mono">
                      <span className="lb-tag">{r.role}</span>
                    </td>
                    <td>{r.display_name}</td>
                    <td className="mono">{r.collection}</td>
                    <td className="mono">{r.harness_version}</td>
                    <td className="num">{r.games}</td>
                    <td className="num mono">
                      {r.levels_solved}/{r.levels_attempted}
                    </td>
                    <td className="num">{fmtPct(r.level_solve_rate)}</td>
                    <td className="num mono">
                      {fmtFloat(r.score, 3)}{' '}
                      {r.score_ci_low != null && r.score_ci_high != null && (
                        <span className="muted">
                          [{fmtFloat(r.score_ci_low, 3)}, {fmtFloat(r.score_ci_high, 3)}]
                        </span>
                      )}
                    </td>
                    <td className="num">{fmtPct(r.no_effect_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="lb-subset-note mono">
          Diagnostic finding (PLAN §3.3 Step 0): SFT v1 trained on optimal action sequences without discovery rationales learns JSON syntax (0 parse errors) but scores 0.012 on held-out eval-v1 (56.8% wall-bump loops) — motivating SFT v2 causal rationales + auxiliary world-modelling tasks + GRPO.
        </div>
      </Panel>

      <Panel
        label="Outside Reasoning Transfer Suite (FT_BENCHMARKS.md · PROTOCOL v3 · Qwen3.5-9B)"
        actions={
          candidates.length > 0 || hasCheckpoints ? (
            <div className="lb-filter-group">
              {candRun?.scoring_mode === 'v3' && (
                <span className="lb-tag" title="Canonical PROTOCOL v3 rescorer (accepts ANSWER: X on [invalid] extractions; 0 base items changed)">
                  v3 rescored
                </span>
              )}
              <span className="kicker lb-filter-label">Candidate</span>
              {candidates.map((c) => (
                <Button
                  key={c.row_id}
                  mono
                  active={activeCand === c.row_id}
                  onClick={() => setSelectedCand(c.row_id)}
                >
                  {c.row_id}
                  {c.dev_slice ? ' · dev' : ''}
                </Button>
              ))}
              {hasCheckpoints && (
                <Button
                  mono
                  active={showCheckpoints}
                  onClick={() => setShowCheckpoints((prev) => !prev)}
                >
                  {showCheckpoints ? 'hide steps' : 'all steps'}
                </Button>
              )}
            </div>
          ) : (
            <span className="mono muted">lm-eval 0.4.13 · vLLM 0.33 · max_gen_toks=8192</span>
          )
        }
      >
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Suite Group</th>
                <th>Benchmark</th>
                <th>Setting</th>
                <th className="num">
                  base{candRun?.dev_slice && baseRun && !baseRun.dev_slice ? ' (shared)' : ''}
                </th>
                <th className="num">
                  {ctrlRun ? `${ctrlRun.row_id} (ctrl)` : 'ctrl / think-ctrl'}
                </th>
                <th className="num">
                  {candRun ? candRun.row_id : 'think-games / mix'}
                  {candRun?.dev_slice ? ' [dev]' : ''}
                </th>
                <th className="num">Paired Δ vs ctrl [95% CI]</th>
                <th className="num">Paired Δ vs base [95% CI]</th>
                <th className="num">Truncated / Shared</th>
              </tr>
            </thead>
            <tbody>
              {(bench?.suite_definition ?? []).map((item) => {
                const bCell = baseRun?.benchmarks?.[item.id]
                const cCell = ctrlRun?.benchmarks?.[item.id]
                const mCell = candRun?.benchmarks?.[item.id]
                const dCtrl: BenchDeltaCell | undefined = vsCtrl?.benchmarks?.[item.id]
                const dBase: BenchDeltaCell | undefined = vsBase?.benchmarks?.[item.id]
                const useSharedBase = Boolean(
                  candRun?.dev_slice && baseRun && !baseRun.dev_slice && dBase?.mean_ref != null,
                )
                const useSharedCtrl = Boolean(
                  candRun?.dev_slice && ctrlRun && !ctrlRun.dev_slice && dCtrl?.mean_ref != null,
                )
                const bVal = useSharedBase ? dBase?.mean_ref : bCell?.mean
                const cVal = useSharedCtrl ? dCtrl?.mean_ref : cCell?.mean
                const mVal = mCell?.mean
                const showCtrlRaw =
                  !useSharedCtrl &&
                  cCell?.official_mean != null &&
                  cCell?.mean != null &&
                  Math.abs(cCell.mean - cCell.official_mean) >= 0.0005
                const showCandRaw =
                  mCell?.official_mean != null &&
                  mCell?.mean != null &&
                  Math.abs(mCell.mean - mCell.official_mean) >= 0.0005
                return (
                  <tr key={item.id}>
                    <td className="mono muted">{GROUP_LABEL[item.group] ?? item.group}</td>
                    <td>
                      <strong>{item.label}</strong>
                    </td>
                    <td className="mono">{item.setting}</td>
                    <td className="num mono">
                      {bVal != null ? fmtPct(bVal) : <span className="muted">pending</span>}
                    </td>
                    <td className="num mono">
                      {cVal != null ? (
                        <>
                          {fmtPct(cVal)}
                          {showCtrlRaw && (
                            <span className="muted" style={{ display: 'block', fontSize: '10px' }}>
                              raw {fmtPct(cCell?.official_mean)}
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="muted">pending</span>
                      )}
                    </td>
                    <td className="num mono">
                      {mVal != null ? (
                        <>
                          {fmtPct(mVal)}
                          {showCandRaw && (
                            <span className="muted" style={{ display: 'block', fontSize: '10px' }}>
                              raw {fmtPct(mCell?.official_mean)}
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="muted">pending</span>
                      )}
                    </td>
                    <td className={cx('num mono', dCtrl?.excludes_zero && 'lb-best')}>
                      {dCtrl?.delta != null ? (
                        <>
                          {fmtSigned(dCtrl.delta * 100, 1)} pp{' '}
                          {dCtrl.ci_low != null && dCtrl.ci_high != null && (
                            <span className="muted">
                              [{fmtSigned(dCtrl.ci_low * 100, 1)}, {fmtSigned(dCtrl.ci_high * 100, 1)}]
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className={cx('num mono', dBase?.excludes_zero && 'lb-best')}>
                      {dBase?.delta != null ? (
                        <>
                          {fmtSigned(dBase.delta * 100, 1)} pp{' '}
                          {dBase.ci_low != null && dBase.ci_high != null && (
                            <span className="muted">
                              [{fmtSigned(dBase.ci_low * 100, 1)}, {fmtSigned(dBase.ci_high * 100, 1)}]
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="num mono">
                      {mCell != null || bCell != null ? (
                        <>
                          {`${bCell?.truncated ?? 0} / ${mCell?.truncated ?? 0}`}
                          {candRun?.dev_slice && dBase?.n_shared ? (
                            <span className="muted"> ({dBase.n_shared})</span>
                          ) : null}
                        </>
                      ) : (
                        item.items ?? 'full'
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="lb-subset-note mono">
          PROTOCOL v3 (bench/PROTOCOL.md · DECISIONS.md Sat 21:15): canonical rescorer accepts &quot;ANSWER: X&quot; on [invalid] lm-eval extractions (0 base items changed; raw lm-eval scores shown inline where rescored). Line 1 answer-only SFT v2 suppressed &lt;think&gt; chains and dropped Qwen3.5-9B primary headline (~75.8% → ~44.1% negative result); Line 2 runs Thinking-On GRPO directly from base (think-games vs matched think-ctrl on shared items).
        </div>
      </Panel>

      {(modeWeights.length > 0 || ruleWeights.length > 0) && (
        <div className="lb-two-col">
          <Panel
            label="Failure-Mode Oversampling Weights (A5-21 → A1/A3)"
            actions={
              <span className="mono muted">
                {decisionPoints?.train_safe_decision_points ?? decisionPoints?.total_decision_points ?? 0} dev-safe points
              </span>
            }
          >
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Failure Mode</th>
                    <th className="num">Observed Count</th>
                    <th className="num">Sampling Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {modeWeights.map(([mode, w]) => (
                    <tr key={mode}>
                      <td className="mono">{mode}</td>
                      <td className="num mono">{decisionPoints?.failure_mode_counts?.[mode] ?? '—'}</td>
                      <td className="num mono">{fmtPct(w)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel
            label="Rule Bottleneck Weights (Tier-3 Holdouts Excluded)"
            actions={<span className="mono muted">analysis/decision_point_targets.json</span>}
          >
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Rule Mechanic</th>
                    <th className="num">Target Mixture Share</th>
                  </tr>
                </thead>
                <tbody>
                  {ruleWeights.map(([rule, w]) => (
                    <tr key={rule}>
                      <td className="mono">{rule}</td>
                      <td className="num mono">{fmtPct(w)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </div>
  )
}
