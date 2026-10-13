import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { confirmPasswordReset, getBrandPortal, requestPasswordReset } from '../../shared/api/workspace.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { PasswordField, TextField } from '../../shared/ui/Field.tsx'
import { Wordmark } from '../../shared/ui/Wordmark.tsx'
import { useSession } from '../workspace/queries.ts'

export function ForgotPasswordPage() {
  const { brandSlug } = useParams<{ brandSlug: string }>()
  const session = useSession()
  const navigate = useNavigate()
  const [step, setStep] = useState<'confirm' | 'otp'>('confirm')
  const [otp, setOtp] = useState('')
  const [password, setPassword] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  const portal = useQuery({
    queryKey: ['brand-portal', brandSlug],
    queryFn: () => getBrandPortal(brandSlug!),
    enabled: Boolean(brandSlug),
    retry: false,
  })

  usePageTitle(portal.data?.name ? `${portal.data.name} · Reset password` : 'Reset password')

  const requestCode = useMutation({
    mutationFn: () => requestPasswordReset(brandSlug!),
    onSuccess: (data) => {
      setNotice(data.detail)
      setStep('otp')
    },
  })

  const resetPassword = useMutation({
    mutationFn: () =>
      confirmPasswordReset({
        slug: brandSlug!,
        otp: otp.trim(),
        new_password: password,
      }),
    onSuccess: () => {
      navigate(`/b/${brandSlug}/login`, { replace: true })
    },
  })

  if (!brandSlug) return <Navigate to="/login" replace />
  if (session.accessToken || session.preview) return <Navigate to="/" replace />

  const loginTo = `/b/${brandSlug}/login`
  const brandName = portal.data?.name
  const maskedEmail = portal.data?.masked_admin_email

  return (
    <main className="grid min-h-svh place-items-center bg-[var(--brand-background)] px-6 py-12">
      <div className="w-full max-w-sm rounded-3xl border border-line bg-[var(--brand-surface)] p-8 shadow-card">
        <Wordmark />
        <h1 className="mt-6 font-display text-3xl tracking-tight">Reset password</h1>
        <p className="mt-2 text-sm text-ink-soft">
          {brandName ? `Brand Admin for ${brandName}.` : 'Brand Admin password reset.'} A one-time
          code is sent to the Brand Admin email below.
        </p>

        {portal.isError ? (
          <p className="mt-4 text-sm text-danger">This brand portal was not found.</p>
        ) : null}

        {step === 'confirm' ? (
          <form
            className="mt-6 grid gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              requestCode.mutate()
            }}
          >
            <div className="rounded-xl border border-line bg-cream px-3 py-3">
              <p className="text-xs font-medium text-ink-soft">Brand Admin email</p>
              <p className="mt-1 font-medium tracking-wide">
                {portal.isLoading ? 'Loading…' : maskedEmail || '—'}
              </p>
            </div>
            {requestCode.isError ? (
              <p className="text-sm text-danger" role="alert">
                {errorMessage(requestCode.error)}
              </p>
            ) : null}
            <Button type="submit" disabled={requestCode.isPending || portal.isError || portal.isLoading}>
              {requestCode.isPending ? 'Sending…' : 'Send code'}
            </Button>
          </form>
        ) : (
          <form
            className="mt-6 grid gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              resetPassword.mutate()
            }}
          >
            {notice ? <p className="text-sm text-ink-soft">{notice}</p> : null}
            <div className="rounded-xl border border-line bg-cream px-3 py-3">
              <p className="text-xs font-medium text-ink-soft">Code sent to</p>
              <p className="mt-1 font-medium tracking-wide">{maskedEmail || '—'}</p>
            </div>
            <TextField
              label="One-time code"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              minLength={6}
              maxLength={6}
              value={otp}
              onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 6))}
              hint="6-digit code sent to the Brand Admin email."
            />
            <PasswordField
              label="New password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {resetPassword.isError ? (
              <p className="text-sm text-danger" role="alert">
                {errorMessage(resetPassword.error)}
              </p>
            ) : null}
            <Button type="submit" disabled={resetPassword.isPending}>
              {resetPassword.isPending ? 'Updating…' : 'Update password'}
            </Button>
            <button
              type="button"
              className="text-sm font-medium text-[var(--brand-primary)]"
              onClick={() => requestCode.mutate()}
              disabled={requestCode.isPending}
            >
              Resend code
            </button>
          </form>
        )}

        <p className="mt-6 text-sm text-ink-soft">
          <Link className="font-medium text-[var(--brand-primary)] underline-offset-2 hover:underline" to={loginTo}>
            Back to sign in
          </Link>
        </p>
      </div>
    </main>
  )
}
