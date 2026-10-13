import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { getMe, listOrganizations, superAdminLogin } from '../../shared/api/workspace.ts'
import { queryClient } from '../../shared/api/queryClient.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { PasswordField, TextField } from '../../shared/ui/Field.tsx'
import { Wordmark } from '../../shared/ui/Wordmark.tsx'
import { useSession } from '../workspace/queries.ts'

export function SuperAdminLoginPage() {
  usePageTitle('Super Admin sign in')
  const session = useSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    mutationFn: () => superAdminLogin(email, password),
    onSuccess: async () => {
      const me = await getMe()
      queryClient.setQueryData(['me'], me)
      queryClient.setQueryData(['organizations'], await listOrganizations())
      navigate('/platform/brands')
    },
  })

  if (session.accessToken) return <Navigate to="/platform/brands" replace />

  return (
    <main className="grid min-h-svh place-items-center bg-[var(--brand-background)] px-6 py-12">
      <form
        className="w-full max-w-sm rounded-3xl border border-line bg-[var(--brand-surface)] p-8 shadow-card"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <Wordmark />
        <h1 className="mt-6 font-display text-3xl tracking-tight">Super Admin</h1>
        <p className="mt-2 text-sm text-ink-soft">Platform administration only.</p>
        <div className="mt-6 grid gap-4">
          <TextField
            label="Email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
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
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
        </div>
      </form>
    </main>
  )
}
