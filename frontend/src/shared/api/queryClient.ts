import { QueryClient } from '@tanstack/react-query'

import { ApiError } from './axios'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
        return count < 1
      },
    },
    mutations: {
      retry: false,
    },
  },
})

export const queryKeys = {
  me: ['me'] as const,
  organizations: ['me', 'organizations'] as const,
  context: (orgId: string) => ['tenant', orgId, 'context'] as const,
  members: (orgId: string) => ['tenant', orgId, 'members'] as const,
  roles: (orgId: string) => ['tenant', orgId, 'roles'] as const,
  invitations: (orgId: string) => ['tenant', orgId, 'invitations'] as const,
  branches: (orgId: string) => ['tenant', orgId, 'branches'] as const,
  audit: (orgId: string) => ['tenant', orgId, 'audit'] as const,
  subscription: (orgId: string) => ['tenant', orgId, 'subscription'] as const,
  platformTenants: ['platform', 'tenants'] as const,
  platformPlans: ['platform', 'plans'] as const,
  platformMetrics: ['platform', 'metrics'] as const,
}

export async function resetTenantCache() {
  await queryClient.cancelQueries({ queryKey: ['tenant'] })
  queryClient.removeQueries({ queryKey: ['tenant'] })
}
