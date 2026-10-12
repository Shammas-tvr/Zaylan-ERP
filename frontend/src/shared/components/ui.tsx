import type { ButtonHTMLAttributes, FormEvent, InputHTMLAttributes, ReactNode } from 'react'

export function Page({ title, subtitle, actions, children }: {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">{title}</h1>
          {subtitle ? <p className="mt-1 max-w-2xl text-sm text-ink/70">{subtitle}</p> : null}
        </div>
        {actions}
      </header>
      {children}
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-card border border-line bg-surface p-5 shadow-card ${className}`}>
      {children}
    </section>
  )
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }) {
  const styles = {
    primary: 'bg-burgundy text-surface hover:bg-[#5a2626]',
    secondary: 'border border-line bg-surface text-ink hover:bg-surface-muted',
    ghost: 'text-burgundy hover:bg-burgundy/10',
  }[variant]
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  )
}

export function Field({
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-semibold text-ink">{label}</span>
      <input
        className="rounded-lg border border-line bg-surface px-3 py-2 text-ink"
        {...props}
      />
    </label>
  )
}

export function Alert({ children, tone = 'danger' }: { children: ReactNode; tone?: 'danger' | 'success' }) {
  const styles = tone === 'success' ? 'border-success/40 bg-success/10 text-success' : 'border-danger/40 bg-danger/10 text-danger'
  return <div role="alert" className={`rounded-lg border px-3 py-2 text-sm ${styles}`}>{children}</div>
}

export function Form({ onSubmit, children }: { onSubmit: (event: FormEvent<HTMLFormElement>) => void; children: ReactNode }) {
  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      {children}
    </form>
  )
}

export function StatusPill({ value }: { value: string }) {
  return (
    <span className="inline-flex rounded-full border border-line bg-surface-muted px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-ink">
      {value.toLowerCase().replaceAll('_', ' ')}
    </span>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-ink/70">{children}</p>
}
