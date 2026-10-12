import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../labels.ts'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'md' | 'sm'
}

const variants = {
  primary: 'bg-[var(--brand-primary)] text-[var(--brand-on-primary)] hover:opacity-90',
  secondary: 'border border-line bg-[var(--brand-surface)] text-ink hover:bg-cream-deep',
  ghost: 'text-ink hover:bg-cream-deep',
  danger: 'border border-danger/20 bg-danger-soft text-danger hover:bg-danger-soft/80',
}

const sizes = {
  md: 'h-11 px-4 text-sm',
  sm: 'h-9 px-3 text-sm',
}

export function Button({ variant = 'primary', size = 'md', className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  )
}
