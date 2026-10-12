import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../../shared/api/axios'
import { Alert, Button, Card, Field, Form } from '../../shared/components/ui'
import { useAuth } from './AuthProvider'

export function LoginPage() {
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setPending(true)
    setError('')
    try {
      await signIn(String(data.get('email')), String(data.get('password')))
      const to = (location.state as { from?: string } | null)?.from || '/'
      navigate(to, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to sign in.')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthScreen title="Welcome back" subtitle="Sign in to Zaylan to manage your organization.">
      <Form onSubmit={onSubmit}>
        {error ? <Alert>{error}</Alert> : null}
        <Field label="Email" name="email" type="email" autoComplete="username" required />
        <Field label="Password" name="password" type="password" autoComplete="current-password" required />
        <Button type="submit" disabled={pending}>{pending ? 'Signing in…' : 'Sign in'}</Button>
      </Form>
      <p className="mt-4 text-sm text-ink/70">
        Have an invite? <Link className="font-semibold text-burgundy" to="/invitations/accept">Accept invitation</Link>
      </p>
    </AuthScreen>
  )
}

export function AuthScreen({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <p className="mb-6 text-center font-display text-3xl font-semibold text-burgundy">Zaylan</p>
        <Card>
          <h1 className="font-display text-2xl font-semibold">{title}</h1>
          <p className="mb-5 mt-1 text-sm text-ink/70">{subtitle}</p>
          {children}
        </Card>
      </div>
    </div>
  )
}
