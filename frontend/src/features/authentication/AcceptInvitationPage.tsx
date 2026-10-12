import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { authApi } from '../../shared/api/client'
import { ApiError } from '../../shared/api/axios'
import { Alert, Button, Field, Form } from '../../shared/components/ui'
import { useAuth } from './AuthProvider'
import { AuthScreen } from './LoginPage'

function readToken() {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const query = new URLSearchParams(window.location.search)
  return hash.get('token') || query.get('token') || ''
}

export function AcceptInvitationPage() {
  const token = useMemo(readToken, [])
  const { user, completeSession } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const lookup = useQuery({
    queryKey: ['invitation', token],
    queryFn: () => authApi.lookupInvitation(token),
    enabled: Boolean(token),
    retry: false,
  })

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setError('')
    try {
      const session = await authApi.acceptInvitation({
        token,
        full_name: String(data.get('full_name') || ''),
        password: String(data.get('password') || ''),
      })
      await completeSession(session.access, session.user, session.organization_id)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to accept this invitation.')
    }
  }

  if (!token) {
    return (
      <AuthScreen title="Invitation required" subtitle="Open the invitation link from your email.">
        <Alert>No invitation token was found in this URL.</Alert>
      </AuthScreen>
    )
  }

  if (lookup.isError) {
    return (
      <AuthScreen title="Invitation unavailable" subtitle="This link is invalid, used, or expired.">
        <Alert>{lookup.error instanceof ApiError ? lookup.error.message : 'Unable to open this invitation.'}</Alert>
      </AuthScreen>
    )
  }

  const needsAccount = lookup.data && !lookup.data.account_exists && !user

  return (
    <AuthScreen
      title="Join your organization"
      subtitle={lookup.data ? `You were invited to ${lookup.data.organization_name} as ${lookup.data.email}.` : 'Checking invitation…'}
    >
      <Form onSubmit={onSubmit}>
        {error ? <Alert>{error}</Alert> : null}
        {needsAccount ? (
          <>
            <Field label="Full name" name="full_name" required />
            <Field label="Password" name="password" type="password" autoComplete="new-password" required minLength={10} />
          </>
        ) : null}
        {lookup.data?.account_exists && !user ? (
          <Alert>Sign in with {lookup.data.email} first, then return to this invitation link.</Alert>
        ) : (
          <Button type="submit" disabled={lookup.isLoading}>Accept invitation</Button>
        )}
      </Form>
    </AuthScreen>
  )
}
