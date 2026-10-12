import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { authApi } from '../../shared/api/client'
import { refreshAccessToken } from '../../shared/api/axios'
import { queryKeys, resetTenantCache } from '../../shared/api/queryClient'
import type { User } from '../../shared/api/types'
import {
  clearSession,
  getAccessToken,
  getOrganizationId,
  setAccessToken,
  setOrganizationId,
} from '../../shared/session'

type AuthState = {
  user: User | null
  ready: boolean
  organizationId: string | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  selectOrganization: (id: string) => Promise<void>
  completeSession: (access: string, user: User, organizationId?: string) => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [ready, setReady] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [organizationId, setOrg] = useState<string | null>(getOrganizationId())

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const token = getAccessToken() || (await refreshAccessToken())
      if (!cancelled && token) {
        try {
          setUser(await authApi.me())
        } catch {
          clearSession()
          setUser(null)
        }
      }
      if (!cancelled) setReady(true)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const completeSession = useCallback(
    async (access: string, nextUser: User, orgId?: string) => {
      setAccessToken(access)
      setUser(nextUser)
      if (orgId) {
        setOrganizationId(orgId)
        setOrg(orgId)
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.me })
    },
    [queryClient],
  )

  const signIn = useCallback(
    async (email: string, password: string) => {
      const session = await authApi.login(email, password)
      await completeSession(session.access, session.user)
    },
    [completeSession],
  )

  const signOut = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      clearSession()
      setUser(null)
      setOrg(null)
      queryClient.clear()
    }
  }, [queryClient])

  const selectOrganization = useCallback(async (id: string) => {
    await resetTenantCache()
    setOrganizationId(id)
    setOrg(id)
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      ready,
      organizationId,
      completeSession,
      signIn,
      signOut,
      selectOrganization,
    }),
    [completeSession, organizationId, ready, selectOrganization, signIn, signOut, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('AuthProvider is missing')
  return ctx
}

export function useOrganizations() {
  const { user } = useAuth()
  return useQuery({
    queryKey: queryKeys.organizations,
    queryFn: authApi.organizations,
    enabled: Boolean(user),
  })
}
