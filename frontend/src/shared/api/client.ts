import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { sessionStore } from '../session.ts'
import { toApiError } from './errors.ts'
import { queryClient } from './queryClient.ts'

const raw = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
export const apiBaseUrl = raw.endsWith('/api/v1') ? raw : `${raw}/api/v1`

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean }

export const client = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  timeout: 15_000,
})

const refreshClient = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  timeout: 15_000,
})

let refreshPromise: Promise<string | null> | null = null

export function refreshAccess() {
  if (!refreshPromise) {
    refreshPromise = refreshClient
      .post<{ access: string }>('/auth/refresh')
      .then((response) => response.data.access)
      .catch(() => null)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

client.interceptors.request.use((config) => {
  const session = sessionStore.get()
  if (session.accessToken) config.headers.set('Authorization', `Bearer ${session.accessToken}`)
  if (session.organizationId) config.headers.set('X-Organization-ID', session.organizationId)
  return config
})

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined
    const url = original?.url ?? ''
    const isAuthCall =
      url.includes('/auth/login') || url.includes('/auth/refresh') || url.includes('/auth/logout')
    if (error.response?.status === 401 && original && !original._retry && !isAuthCall) {
      original._retry = true
      const access = await refreshAccess()
      if (access) {
        sessionStore.set({ accessToken: access })
        original.headers.set('Authorization', `Bearer ${access}`)
        return client(original)
      }
      sessionStore.clear()
      queryClient.clear()
    }
    return Promise.reject(toApiError(error))
  },
)
