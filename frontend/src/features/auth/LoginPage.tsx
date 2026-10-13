import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { getBrandPortal, getMe, listOrganizations, login } from '../../shared/api/workspace.ts'
import { queryClient } from '../../shared/api/queryClient.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { apiBaseUrl } from '../../shared/api/client.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { PasswordField, TextField } from '../../shared/ui/Field.tsx'
import { Wordmark } from '../../shared/ui/Wordmark.tsx'
import { selectOrganization, useSession } from '../workspace/queries.ts'

export function LoginPage() {
  const { brandSlug } = useParams<{ brandSlug?: string }>()
  const session = useSession()
  const navigate = useNavigate()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')

  const portal = useQuery({
    queryKey: ['brand-portal', brandSlug],
    queryFn: () => getBrandPortal(brandSlug!),
    enabled: Boolean(brandSlug),
    retry: false,
  })

  const brandName = portal.data?.name
  usePageTitle(brandName ? `${brandName} · Sign in` : 'Sign in')

  const mutation = useMutation({
    mutationFn: () => login(identifier, password),
    onSuccess: async () => {
      const [organizations, me] = await Promise.all([listOrganizations(), getMe()])
      queryClient.setQueryData(['organizations'], organizations)
      queryClient.setQueryData(['me'], me)
      if (organizations[0]) {
        selectOrganization(organizations[0].id)
        navigate('/')
        return
      }
      navigate('/')
    },
  })

  if (session.accessToken || session.preview) return <Navigate to="/" replace />

  const forgotTo = brandSlug ? `/b/${brandSlug}/forgot-password` : null

  return (
    <main className="grid min-h-svh lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
      <section className="relative flex flex-col justify-between overflow-hidden px-6 py-8 sm:px-12 sm:py-12">
        <div className="pointer-events-none absolute -left-20 -top-24 size-80 rounded-full bg-[var(--brand-secondary)]/25" />
        <Wordmark />
        <div className="relative max-w-md py-16">
          <h1 className="font-display text-5xl leading-tight tracking-tight sm:text-6xl">
            {brandName ?? 'Operations for every branch.'}
          </h1>
          <p className="mt-5 max-w-sm text-lg text-ink-soft">
            {brandName
              ? 'Brand Admin and branch staff sign in here.'
              : 'Open your brand portal link (/b/your-slug) to sign in.'}
          </p>
          <span className="mt-8 block h-0.5 w-12 bg-[var(--brand-secondary)]" />
        </div>
        <p className="relative text-sm text-ink-soft">Point of sale · Inventory · Profitability</p>
      </section>
      <section className="flex items-center bg-[var(--brand-surface)] px-6 py-12 sm:px-12">
        <form
          className="mx-auto grid w-full max-w-sm gap-5"
          onSubmit={(event) => {
            event.preventDefault()
            mutation.mutate()
          }}
        >
          <div>
            <h2 className="font-display text-3xl tracking-tight">Sign in</h2>
            <p className="mt-2 text-sm text-ink-soft">
              {brandName
                ? `Signing in to ${brandName}. Use Brand Admin email or staff username.`
                : 'Brand Admin email or staff username.'}
            </p>
            {brandSlug && portal.isError ? (
              <p className="mt-2 text-sm text-danger">This brand portal was not found.</p>
            ) : null}
          </div>
          <TextField
            label="Email or username"
            autoComplete="username"
            required
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
          />
          <PasswordField
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {mutation.isError ? (
            <p className="text-sm text-danger" role="alert">
              {errorMessage(mutation.error)}
            </p>
          ) : null}
          <Button type="submit" disabled={mutation.isPending || Boolean(brandSlug && portal.isError)}>
            {mutation.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
          {forgotTo ? (
            <p className="text-sm text-ink-soft">
              <Link
                className="font-medium text-[var(--brand-primary)] underline-offset-2 hover:underline"
                to={forgotTo}
              >
                Forgot password?
              </Link>
            </p>
          ) : null}
          <p className="text-xs text-ink-soft">API {apiBaseUrl}</p>
        </form>
      </section>
    </main>
  )
}
