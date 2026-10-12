import { useQuery } from '@tanstack/react-query'
import { createContext, useContext, useEffect, type ReactNode } from 'react'

import { authApi } from '../../shared/api/client'
import { queryKeys } from '../../shared/api/queryClient'
import type { TenantContext } from '../../shared/api/types'
import { useAuth } from '../authentication/AuthProvider'

const TenantState = createContext<TenantContext | null>(null)

export function TenantProvider({ children }: { children: ReactNode }) {
  const { organizationId } = useAuth()
  const query = useQuery({
    queryKey: queryKeys.context(organizationId || 'none'),
    queryFn: authApi.context,
    enabled: Boolean(organizationId),
  })

  useEffect(() => {
    const branding = query.data?.branding
    const root = document.documentElement
    if (!branding) return
    root.style.setProperty('--tenant-primary', branding.primary_color)
    root.style.setProperty('--tenant-secondary', branding.secondary_color)
    root.style.setProperty('--tenant-background', branding.background_color)
    root.style.setProperty('--tenant-surface', branding.surface_color)
    root.style.setProperty('--tenant-text', branding.text_color)
    root.setAttribute('data-theme', 'tenant')
  }, [query.data])

  if (!organizationId) return null
  if (query.isLoading) return <p className="p-8 text-sm text-ink/70">Loading organization…</p>
  if (query.isError || !query.data) {
    return <p className="p-8 text-sm text-danger">This organization is not available.</p>
  }

  return <TenantState.Provider value={query.data}>{children}</TenantState.Provider>
}

export function useTenant() {
  const ctx = useContext(TenantState)
  if (!ctx) throw new Error('TenantProvider is missing')
  return ctx
}

export function can(ctx: TenantContext, permission: string) {
  return ctx.tenant_permissions.includes(permission) || ctx.branches.some((b) => b.permissions.includes(permission))
}
