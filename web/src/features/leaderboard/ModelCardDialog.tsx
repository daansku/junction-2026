import { useEffect, useRef } from 'react'
import { Swatch } from '@/design/primitives'
import type { LeaderboardRow } from './types'

function fmtFloat(v: number | null | undefined, digits = 3): string | null {
  if (v == null || Number.isNaN(v)) return null
  return v.toFixed(digits)
}

function fmtPct(v: number | null | undefined): string | null {
  if (v == null || Number.isNaN(v)) return null
  return `${(v * 100).toFixed(1)}%`
}

function fmtTokens(v: number | null | undefined): string | null {
  if (v == null || Number.isNaN(v) || v <= 0) return null
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${Math.round(v / 1_000)}k`
  return String(Math.round(v))
}

/** Player name without the " [collection]" suffix, plus effort. */
export function cardLabel(row: LeaderboardRow): string {
  const base = (row.display_name || row.model?.display_name || row.player_id).replace(` [${row.collection}]`, '')
  return row.effort ? `${base} (${row.effort})` : base
}

export type CardEntry = [string, string | null | undefined]

/**
 * Model card shown when a player name is clicked on the leaderboard.
 * Empty values are hidden, so the same card works for h1 and h2 rows.
 */
export function ModelCardDialog({
  row,
  color,
  extra = [],
  onClose,
}: {
  row: LeaderboardRow
  color: string
  extra?: CardEntry[]
  onClose: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current
    if (el && !el.open) el.showModal()
  }, [])

  const card = row.model
  const modes = row.input_modes ?? card?.input_modes
  const price =
    card?.pricing_per_mtok ??
    (card?.price_in != null && card?.price_out != null ? { in: card.price_in, out: card.price_out } : null)
  const facts: CardEntry[] = [
    ['Provider', card?.provider || row.provider],
    ['Tier', card?.tier ?? row.tier ?? row.kind],
    ['Input', modes?.length ? modes.join('+') : null],
    ['Effort', row.effort || card?.default_effort],
    ['Params', card?.params ?? (card?.params_b != null ? `${card.params_b}B` : null)],
    ['Context', card?.context_window ? `${fmtTokens(card.context_window)} tokens` : null],
    ['Price / Mtok', price ? `$${price.in} in · $${price.out} out` : null],
    ['Released', card?.release_date],
  ]
  const tokensIn = fmtTokens(row.tokens_in)
  const tokensOut = fmtTokens(row.tokens_out)
  const stats: CardEntry[] = [
    ['Score', fmtFloat(row.score)],
    ['Levels solved', `${row.levels_solved}/${row.levels_attempted}`],
    ['vs Human', fmtFloat(row.rhae_vs_human)],
    ...extra,
    ['Seen games', fmtFloat(row.seen_score)],
    ['Unseen pair', fmtFloat(row.unseen_pair_score)],
    ['Unseen skin', fmtFloat(row.unseen_skin_score)],
    ['No-effect actions', fmtPct(row.no_effect_rate)],
    ['Belief accuracy', fmtPct(row.belief_accuracy)],
    ['Resets', row.resets_total != null ? String(row.resets_total) : null],
    ['Tokens in / out', tokensIn || tokensOut ? `${tokensIn ?? '—'} / ${tokensOut ?? '—'}` : null],
    ['Latency (median)', row.latency_ms_median != null ? `${Math.round(row.latency_ms_median)} ms` : null],
  ]

  const grid = (entries: CardEntry[]) => (
    <dl className="lb-card-grid mono">
      {entries
        .filter(([, v]) => v)
        .map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
    </dl>
  )

  return (
    <dialog
      ref={ref}
      className="lb-card-dialog"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close()
      }}
    >
      <div className="lb-card-body">
        <header className="lb-card-head">
          <Swatch color={color} />
          <strong>{cardLabel(row)}</strong>
          <span className="lb-tag">{row.collection}</span>
          <button type="button" className="lb-card-close" aria-label="Close" onClick={() => ref.current?.close()}>
            ×
          </button>
        </header>
        {grid(facts)}
        {grid(stats)}
        {row.subset_note && <p className="lb-card-note">{row.subset_note}</p>}
        {card?.notes && <p className="lb-card-note">{card.notes}</p>}
        {card?.link && (
          <a href={card.link} target="_blank" rel="noreferrer" className="mono">
            model page →
          </a>
        )}
      </div>
    </dialog>
  )
}
