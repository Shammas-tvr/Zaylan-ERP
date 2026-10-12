import type { ReactNode } from 'react'
import { errorMessage } from '../api/errors.ts'
import { Button } from './Button.tsx'

export function PageSkeleton() {
  return (
    <div className="grid gap-4" aria-hidden="true">
      <div className="h-10 w-56 rounded-2xl bg-cream-deep" />
      <div className="h-40 rounded-3xl bg-cream-deep" />
      <div className="h-40 rounded-3xl bg-cream-deep" />
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="rounded-3xl border border-line bg-[var(--brand-surface)] p-6" role="alert">
      <h2 className="font-display text-2xl">This page could not be loaded</h2>
      <p className="mt-2 text-ink-soft">{errorMessage(error)}</p>
      {onRetry ? (
        <Button className="mt-4" variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  )
}

export function NoAccess({ children }: { children?: ReactNode }) {
  return (
    <div className="rounded-3xl border border-line bg-[var(--brand-surface)] p-6">
      <h2 className="font-display text-2xl">This area is restricted</h2>
      <p className="mt-2 max-w-xl text-ink-soft">
        {children ?? 'Your role does not include access to this page. An owner can grant it from People.'}
      </p>
    </div>
  )
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl bg-cream-deep px-4 py-3 text-sm text-ink" role="status">
      {children}
    </p>
  )
}
