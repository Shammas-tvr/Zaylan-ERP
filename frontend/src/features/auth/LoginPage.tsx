import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { ZAYLAN_ID } from '../preview/data.ts'
import { resetPreview } from '../preview/store.ts'
import { listOrganizations, login } from '../../shared/api/workspace.ts'
import { queryClient } from '../../shared/api/queryClient.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { apiBaseUrl } from '../../shared/api/client.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { sessionStore } from '../../shared/session.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
import { Wordmark } from '../../shared/ui/Wordmark.tsx'
import { selectOrganization, useSession } from '../workspace/queries.ts'

export function LoginPage() {
  usePageTitle('Sign in')
  const session = useSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: async () => {
      const organizations = await listOrganizations()
      queryClient.setQueryData(['organizations'], organizations)
      if (organizations[0]) selectOrganization(organizations[0].id)
      navigate('/')
    },
  })

  if (session.accessToken || session.preview) return <Navigate to="/" replace />

  return (
    <main className="grid min-h-svh lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
      <section className="relative flex flex-col justify-between overflow-hidden px-6 py-8 sm:px-12 sm:py-12">
        <div className="pointer-events-none absolute -left-20 -top-24 size-80 rounded-full bg-[var(--brand-secondary)]/25" />
        <Wordmark />
        <div className="relative max-w-md py-16">
          <h1 className="font-display text-5xl leading-tight tracking-tight sm:text-6xl">Operations for every branch.</h1>
          <p className="mt-5 max-w-sm text-lg text-ink-soft">
            Billing, inventory, costing, and approvals — kept separate for each business.
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
            <p className="mt-2 text-sm text-ink-soft">Use the email address for your Zaylan account.</p>
          </div>
          <TextField
            label="Email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <TextField
            label="Password"
            type="password"
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
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
          {import.meta.env.DEV ? (
            <Button
              variant="secondary"
              onClick={() => {
                resetPreview()
                queryClient.clear()
                sessionStore.set({ preview: true, accessToken: null, organizationId: ZAYLAN_ID, branchId: null })
                navigate('/')
              }}
            >
              Open a sample workspace
            </Button>
          ) : null}
          <p className="text-xs text-ink-soft">API {apiBaseUrl}</p>
        </form>
      </section>
    </main>
  )
}
