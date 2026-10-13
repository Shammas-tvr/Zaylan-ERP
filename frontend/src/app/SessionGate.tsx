import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { refreshAccess } from '../shared/api/client.ts'
import { sessionStore } from '../shared/session.ts'
import { Wordmark } from '../shared/ui/Wordmark.tsx'
import { useSession } from '../features/workspace/queries.ts'

export function SessionGate() {
  const session = useSession()
  const [ready, setReady] = useState(session.preview)

  useEffect(() => {
    if (sessionStore.get().preview) {
      setReady(true)
      return
    }
    let cancelled = false
    refreshAccess().then((access) => {
      if (cancelled) return
      if (access) sessionStore.set({ accessToken: access })
      setReady(true)
    })
    return () => {
      cancelled = true
    }
  }, [])

  if (!ready) {
    return (
      <div className="grid min-h-svh place-items-center">
        <Wordmark />
      </div>
    )
  }
  return <Outlet />
}

export function RequireSession() {
  const session = useSession()
  const location = useLocation()
  if (!session.accessToken && !session.preview) {
    const to = location.pathname.startsWith('/platform') ? '/superadmin/login' : '/login'
    return <Navigate to={to} replace />
  }
  return <Outlet />
}
