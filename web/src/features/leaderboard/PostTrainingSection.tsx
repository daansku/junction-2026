import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Chip, Empty, Loading, Panel, Stat, Swatch, cx } from '@/design/primitives'
import { cssVar, seriesColors } from '@/lib/PlotFigure'
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
  if (v < 0.01) return `$${v.toFixed(4)}`
  return `$${v.toFixed(2)}`
}

function fmtTokens(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}k`
  return `${Math.round(v)}`
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

export function LeaderboardH2View(props: {
  doc?: LeaderboardH2Document
  isLoading?: boolean
  resolveRunFallback: (row: LeaderboardRow) => string | null
}) {
  const { doc, isLoading, resolveRunFallback } = props
  const [collection, setCollection] = useState<string>('all')

  const allRows = doc?.rows ?? []
  const collections = useMemo(() => {
    const s = new Set<string>()
    for (const r of allRows) s.add(r.collection || 'eval-v1')
    return ['all', ...Array.from(s).sort()]
  }, [allRows])

  const filteredRows = useMemo(() => {
    if (collection === 'all') return allRows
    return allRows.filter((r) => r.collection === collection)
  }, [allRows, collection])

  const kpi = useMemo(() => {
    const models = filteredRows.filter((r) => r.kind === 'model')
    const best = models.reduce<LeaderboardRow | null>(
      (acc, cur) => (!acc || cur.score > acc.score ? cur : acc),
      null,
    )
    const fullSetBest = models
      .filter((r) => r.games >= 2)
      .reduce<LeaderboardRow | null>((acc, cur) => (!acc || cur.score > acc.score ? cur : acc), null)
    const human = filteredRows.find((r) => r.kind === 'human')
    const totalGames = models.reduce((acc, r) => acc + (r.games || 0), 0)
    return { modelsCount: models.length, best, fullSetBest: fullSetBest ?? best, human, totalGames }
  }, [filteredRows])

  if (isLoading && !doc) {
    return <Loading what="Loading lab-standard h2 leaderboard" />
  }

  return (
    <div className="lb-stack">
      <Panel
        label="Lab-Standard Evaluation Protocol (h2 · PLAN §3.1)"
        actions={<span className="mono muted">strictly separated from h1 · zero hidden-rule leakage</span>}
      >
        <div className="lb-h2-rules-grid">
          {(doc?.h2_rules ?? []).map((rule, i) => {
            const colon = rule.indexOf(':')
            const head = colon > 0 ? rule.slice(0, colon) : `Rule ${i + 1}`
            const body = colon > 0 ? rule.slice(colon + 1).trim() : rule
            return (
              <div key={i} className="lb-h2-rule-cell">
                <span className="mono lb-h2-rule-head">
                  {String(i + 1).padStart(2, '0')} · {head}
                </span>
                <span className="lb-h2-rule-body">{body}</span>
              </div>
            )
          })}
        </div>
      </Panel>

      {allRows.length === 0 ? (
        <Panel label="Lab-Standard h2 Ledger">
          <Empty>
            No h2 runs are published on this snapshot yet. Run{' '}
            <code className="mono">python -m analysis build</code> or wait for A2 to refresh{' '}
            <code className="mono">/api/derived/leaderboard_h2.json</code>.
          </Empty>
        </Panel>
      ) : (
        <>
          <div className="lb-kpi-grid">
            <div className="lb-kpi-cell">
              <Stat
                label="Best Multi-Game h2 Model"
                value={kpi.fullSetBest ? fmtFloat(kpi.fullSetBest.score, 3) : '—'}
                sub={
                  kpi.fullSetBest
                    ? `${rowLabel(kpi.fullSetBest)} · 95% CI [${fmtFloat(kpi.fullSetBest.score_ci_low, 3)}, ${fmtFloat(kpi.fullSetBest.score_ci_high, 3)}]`
                    : 'No h2 model rows'
                }
              />
            </div>
            <div className="lb-kpi-cell">
              <Stat
                label="Human First-Attempt Ref"
                value={kpi.human ? fmtFloat(kpi.human.score, 3) : '—'}
                sub={
                  kpi.human
                    ? `${kpi.human.display_name || 'Human'} · ${fmtPct(kpi.human.level_solve_rate)} lvl solve`
                    : 'Matched h2 subset'
                }
              />
            </div>
            <div className="lb-kpi-cell">
              <Stat
                label="Optimal BFS Ceiling"
                value="1.000"
                sub="Exact solver shortest path · noop / stop_early = 0.000"
              />
            </div>
            <div className="lb-kpi-cell">
              <Stat
                label="h2 Model Game Runs"
                value={kpi.totalGames}
                unit="games"
                sub={`${kpi.modelsCount} model row(s) · 95% bootstrap CIs`}
              />
            </div>
          </div>

          <div className="lb-controls">
            <div className="lb-filter-group" role="group" aria-label="Filter h2 collection">
              <span className="kicker lb-filter-label">Collection</span>
              {collections.map((c) => (
                <Button
                  key={c}
                  mono
                  active={collection === c}
                  onClick={() => setCollection(c)}
                >
                  {c}
                </Button>
              ))}
            </div>
            <span className="mono muted">
              single-attempt rows badged <code className="mono">k=1</code> · pre-17:35 budget-bug runs excluded
            </span>
          </div>

          <Panel
            label="Lab-Standard h2 Benchmark Ledger"
            actions={<span className="mono muted">{filteredRows.length} rows · 10,000-resample bootstrap 95% CI</span>}
          >
            <div className="table-wrap">
              <table className="table lb-ledger-table">
                <thead>
                  <tr className="lb-group-row">
                    <th colSpan={4} className="lb-group-th">ENTITY &amp; HARNESS RETENTION</th>
                    <th colSpan={4} className="lb-group-th lb-group-sep">OUTCOME &amp; UNCERTAINTY</th>
                    <th colSpan={4} className="lb-group-th lb-group-sep">EFFICIENCY &amp; DIAGNOSTICS</th>
                  </tr>
                  <tr>
                    <th>Player</th>
                    <th>Collection</th>
                    <th>Effort</th>
                    <th>Reasoning Retention</th>
                    <th className="num lb-group-sep">Games</th>
                    <th className="num">Score [95% CI]</th>
                    <th className="num">Lvl Solve</th>
                    <th className="num">Game Win</th>
                    <th className="num lb-group-sep">Med Act</th>
                    <th className="num">Tokens (In / Out)</th>
                    <th className="num">Cost / Game</th>
                    <th className="num">Trace</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row, idx) => {
                    const color = seriesColorFor(row, idx)
                    const runId = row.best_run_id ?? resolveRunFallback(row)
                    const showCi =
                      row.score_ci_low != null &&
                      row.score_ci_high != null &&
                      row.games > 1
                    return (
                      <tr key={`${row.player_id}-${row.collection}-${row.effort ?? 'none'}`}>
                        <td>
                          <div className="lb-player-stack">
                            <div className="lb-player-cell">
                              <Swatch color={color} />
                              <span>{rowLabel(row)}</span>
                              {row.kind === 'model' && (
                                <span
                                  className={cx('lb-tag', row.single_attempt && 'lb-tag-warn')}
                                  title={
                                    row.single_attempt
                                      ? 'Single-attempt evaluation (k=1 run per game)'
                                      : `${row.attempts_per_game ?? 1} attempts per game`
                                  }
                                >
                                  {row.single_attempt ? 'k=1' : `k=${row.attempts_per_game ?? 1}`}
                                </span>
                              )}
                              {row.subset_note && row.subset_note.includes('/') && (
                                <span className="lb-tag" title={row.subset_note}>
                                  subset
                                </span>
                              )}
                            </div>
                            <span className="lb-provider mono">
                              {row.provider || row.kind}
                              {row.max_tokens ? ` · cap ${Math.round(row.max_tokens / 1000)}k` : ''}
                              {row.image_turns ? ` · last-${row.image_turns} frames` : ''}
                            </span>
                          </div>
                        </td>
                        <td className="mono">{row.collection}</td>
                        <td className="mono">{row.effort || '—'}</td>
                        <td className="mono">{formatReasoningMode(row.reasoning_mode)}</td>
                        <td className="num lb-group-sep">
                          {row.games}
                          <span className="muted mono"> ({row.levels_solved}/{row.levels_attempted})</span>
                        </td>
                        <td className="num lb-score-td">
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
                            <span className="mono lb-ci-sub">
                              {showCi
                                ? `[${fmtFloat(row.score_ci_low, 3)}, ${fmtFloat(row.score_ci_high, 3)}]`
                                : row.games === 1 && row.kind === 'model'
                                  ? 'n=1 game'
                                  : '\u00a0'}
                            </span>
                          </div>
                        </td>
                        <td className="num">{fmtPct(row.level_solve_rate)}</td>
                        <td className="num">{fmtPct(row.game_win_rate)}</td>
                        <td className="num lb-group-sep">
                          {row.median_actions != null ? Math.round(row.median_actions) : '—'}
                        </td>
                        <td className="num mono">
                          {row.tokens_in || row.tokens_out
                            ? `${fmtTokens(row.tokens_in)} / ${fmtTokens(row.tokens_out)}`
                            : '—'}
                        </td>
                        <td className="num mono">
                          {row.cost_per_game != null
                            ? fmtUsd(row.cost_per_game)
                            : row.kind === 'model'
                              ? 'credits'
                              : '—'}
                        </td>
                        <td className="num mono">
                          {runId ? (
                            <Link to={`/replay/${encodeURIComponent(runId)}`} className="lb-replay-pill">
                              #{runId.slice(-6)} →
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
            <div className="lb-subset-note mono">
              Even under lab-standard multi-turn retention (h2, effort high/max, 32k–64k output cap, preserved thinking), frontier models trail first-attempt unassisted humans on full 6-game eval-v1 (0.671 vs 0.795) and 8-level eval-v2 (0.463 vs 0.637, 0% vs 100% game wins).
            </div>
          </Panel>
        </>
      )}
    </div>
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
