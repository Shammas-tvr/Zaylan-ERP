import type { ReactNode } from 'react'
import { labelOf, statusLabel } from '../labels.ts'

const tones: Record<string, string> = {
  active: 'bg-success-soft text-success',
  trialing: 'bg-warning-soft text-warning',
  pending: 'bg-warning-soft text-warning',
  suspended: 'bg-danger-soft text-danger',
  deactivated: 'bg-danger-soft text-danger',
  inactive: 'bg-cream-deep text-ink-soft',
  accepted: 'bg-success-soft text-success',
  revoked: 'bg-cream-deep text-ink-soft',
  past_due: 'bg-warning-soft text-warning',
  canceled: 'bg-cream-deep text-ink-soft',
  expired: 'bg-danger-soft text-danger',
  draft: 'bg-cream-deep text-ink-soft',
  pending_approval: 'bg-warning-soft text-warning',
  approved: 'bg-success-soft text-success',
  dispatched: 'bg-warning-soft text-warning',
  received: 'bg-success-soft text-success',
  partially_received: 'bg-warning-soft text-warning',
  closed: 'bg-cream-deep text-ink-soft',
  completed: 'bg-success-soft text-success',
  refunded: 'bg-cream-deep text-ink-soft',
  voided: 'bg-cream-deep text-ink-soft',
  rejected: 'bg-danger-soft text-danger',
  paid: 'bg-success-soft text-success',
  normal: 'bg-success-soft text-success',
  low: 'bg-warning-soft text-warning',
  out: 'bg-danger-soft text-danger',
  unstocked: 'bg-cream-deep text-ink-soft',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${tones[status] ?? 'bg-cream-deep text-ink'}`}
    >
      {labelOf(statusLabel, status)}
    </span>
  )
}

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-3xl border border-line bg-[var(--brand-surface)] p-5 shadow-card sm:p-6 ${className}`}>
      {children}
    </section>
  )
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="font-display text-3xl tracking-tight text-ink sm:text-4xl">{title}</h1>
        {description ? <p className="mt-2 text-ink-soft">{description}</p> : null}
      </div>
      {action}
    </header>
  )
}
