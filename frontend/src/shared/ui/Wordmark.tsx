import { cn, initials } from '../labels.ts'

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-xl bg-[var(--brand-primary)] font-display text-lg text-[var(--brand-on-primary)]">
        Z
      </span>
      {compact ? null : <span className="font-display text-2xl tracking-tight">Zaylan</span>}
    </span>
  )
}

export function Mark({ name }: { name: string }) {
  return (
    <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-cream-deep font-medium text-ink">
      {initials(name)}
    </span>
  )
}

export function MenuButton({
  open,
  onClick,
  className,
}: {
  open: boolean
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      className={cn('grid size-11 place-items-center rounded-xl border border-line bg-[var(--brand-surface)] lg:hidden', className)}
      aria-expanded={open}
      aria-label="Open navigation"
      onClick={onClick}
    >
      <span className="flex w-4 flex-col gap-1">
        <span className="h-px bg-ink" />
        <span className="h-px bg-ink" />
        <span className="h-px bg-ink" />
      </span>
    </button>
  )
}
