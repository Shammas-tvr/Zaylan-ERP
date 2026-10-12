import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './errors.ts'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, error) => {
        if (error instanceof ApiError && error.status < 500) return false
        return count < 1
      },
    },
    mutations: {
      retry: false,
    },
  },
})

const TENANT_ROOTS = new Set(['context', 'members', 'invitations', 'roles', 'audit'])

export function clearTenantQueries() {
  queryClient.removeQueries({
    predicate: (query) => TENANT_ROOTS.has(String(query.queryKey[0])),
  })
  queryClient.cancelQueries({
    predicate: (query) => TENANT_ROOTS.has(String(query.queryKey[0])),
  })
}
