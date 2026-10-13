import { useId, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cn } from '../labels.ts'

const controlClass =
  'w-full rounded-xl border border-line bg-[var(--brand-surface)] px-3 text-ink placeholder:text-ink-soft/70'

export function TextField({
  label,
  hint,
  error,
  ...props
}: { label: string; hint?: string; error?: string } & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId()
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <input id={id} className={cn(controlClass, 'h-11')} aria-invalid={Boolean(error)} {...props} />
    </FieldShell>
  )
}

/** Password input with show/hide and a clear requirement hint by default. */
export function PasswordField({
  label = 'Password',
  hint = 'At least 6 characters.',
  error,
  minLength = 6,
  ...props
}: { label?: string; hint?: string; error?: string } & Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>) {
  const id = useId()
  const [visible, setVisible] = useState(false)
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          className={cn(controlClass, 'h-11 pr-16')}
          aria-invalid={Boolean(error)}
          minLength={minLength}
          {...props}
        />
        <button
          type="button"
          className="absolute inset-y-0 right-2 my-auto h-8 rounded-lg px-2 text-xs font-medium text-ink-soft hover:text-ink"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
        >
          {visible ? 'Hide' : 'Show'}
        </button>
      </div>
    </FieldShell>
  )
}

export function TextArea({
  label,
  hint,
  error,
  ...props
}: { label: string; hint?: string; error?: string } & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId()
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <textarea id={id} className={cn(controlClass, 'min-h-28 py-3')} aria-invalid={Boolean(error)} {...props} />
    </FieldShell>
  )
}

export function SelectField({
  label,
  hint,
  error,
  children,
  ...props
}: { label: string; hint?: string; error?: string; children: ReactNode } & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId()
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <select id={id} className={cn(controlClass, 'h-11')} aria-invalid={Boolean(error)} {...props}>
        {children}
      </select>
    </FieldShell>
  )
}

function FieldShell({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string
  label: string
  hint?: string
  error?: string
  children: ReactNode
}) {
  const messageId = `${id}-message`
  return (
    <div className="grid gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {label}
      </label>
      <div aria-describedby={hint || error ? messageId : undefined}>{children}</div>
      {error ? (
        <p id={messageId} className="text-sm text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="text-sm text-ink-soft">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
