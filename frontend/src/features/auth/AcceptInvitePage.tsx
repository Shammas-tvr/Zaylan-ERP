import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { acceptInvitation } from '../../shared/api/workspace.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { PasswordField, TextField } from '../../shared/ui/Field.tsx'
import { Wordmark } from '../../shared/ui/Wordmark.tsx'

export function AcceptInvitePage() {
  usePageTitle('Accept invitation')
  const [params] = useSearchParams()
  const hashToken = window.location.hash.replace(/^#token=/, '')
  const token = params.get('token') || hashToken
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    mutationFn: () => acceptInvitation({ token, full_name: fullName, password }),
  })

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center px-6 py-12">
      <Wordmark />
      <h1 className="mt-10 font-display text-4xl tracking-tight">Accept invitation</h1>
      {token ? (
        <form
          className="mt-6 grid gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            mutation.mutate()
          }}
        >
          <p className="text-ink-soft">Create your account to join this organization. If you already have an account, sign in with the invited email first.</p>
          <TextField label="Full name" required value={fullName} onChange={(event) => setFullName(event.target.value)} />
          <PasswordField
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {mutation.isError ? <p className="text-sm text-danger">{errorMessage(mutation.error)}</p> : null}
          {mutation.isSuccess ? (
            <p role="status" className="text-sm text-success">
              Invitation accepted. <Link to="/">Continue to your workspace</Link>.
            </p>
          ) : (
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Joining…' : 'Join organization'}
            </Button>
          )}
        </form>
      ) : (
        <p className="mt-4 text-ink-soft">This invitation link is missing a token. Ask the person who invited you to send a new one.</p>
      )}
      <Link to="/login" className="mt-8 text-sm font-medium text-[var(--brand-primary)]">
        Back to sign in
      </Link>
    </main>
  )
}
