import type { ButtonHTMLAttributes, ReactNode } from 'react'
import './primitives.css'

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}

export function Panel(props: {
  label?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  pad?: boolean
}) {
  const { label, actions, children, className, pad = true } = props
  return (
    <section className={cx('panel', className)}>
      {(label || actions) && (
        <header className="panel-head">
          {label && <span className="kicker">{label}</span>}
          {actions && <span className="panel-actions">{actions}</span>}
        </header>
      )}
      <div className={cx('panel-body', pad && 'panel-pad')}>{children}</div>
    </section>
  )
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'primary' | 'ghost'
  mono?: boolean
  active?: boolean
}

export function Button({ variant = 'default', mono, active, className, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      className={cx('btn', `btn-${variant}`, mono && 'mono', active && 'btn-active', className)}
      {...rest}
    />
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>
}

export type Outcome = 'WIN' | 'GAME_OVER' | 'BUDGET' | 'ABORTED' | 'NOT_FINISHED' | string

const OUTCOME_CLASS: Record<string, string> = {
  WIN: 'chip-good',
  GAME_OVER: 'chip-bad',
  BUDGET: 'chip-warn',
  ABORTED: 'chip-muted',
  NOT_FINISHED: 'chip-muted',
}

export function Chip({ outcome, children }: { outcome?: Outcome; children?: ReactNode }) {
  return (
    <span className={cx('chip', outcome ? OUTCOME_CLASS[outcome] ?? 'chip-muted' : 'chip-muted')}>
      {children ?? outcome?.replace('_', ' ')}
    </span>
  )
}

export function Stat(props: { label: ReactNode; value: ReactNode; unit?: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <span className="kicker">{props.label}</span>
      <span className="stat-value">
        {props.value}
        {props.unit && <span className="stat-unit">{props.unit}</span>}
      </span>
      {props.sub && <span className="stat-sub">{props.sub}</span>}
    </div>
  )
}

export function Swatch({ color, title }: { color: string; title?: string }) {
  return <span className="swatch" style={{ background: color }} title={title} aria-hidden={!title} />
}

export function Loading({ what = 'Loading' }: { what?: string }) {
  return <div className="state-line muted">{what}…</div>
}

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="state-line">
      <span className="secondary">{children}</span>
      {action}
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const msg = error instanceof Error ? error.message : String(error)
  return (
    <div className="state-line state-error" role="alert">
      <span>
        <span className="chip chip-bad">ERROR</span> <span className="mono">{msg}</span>
      </span>
      {retry && (
        <Button variant="ghost" onClick={retry}>
          Retry
        </Button>
      )}
    </div>
  )
}

export function PageHeader(props: { title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{props.title}</h1>
        {props.sub && <p className="secondary page-sub">{props.sub}</p>}
      </div>
      {props.actions && <div className="page-actions">{props.actions}</div>}
    </div>
  )
}

export { cx }
