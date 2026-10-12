import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { clearSession, getAccessToken, getOrganizationId, setAccessToken } from '../session'
import type { ApiErrorBody, Session } from './types'

const AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/logout']

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  const orgId = getOrganizationId()
  if (orgId) config.headers['X-Organization-ID'] = orgId
  return config
})

let refreshFlight: Promise<string | null> | null = null

export function refreshAccessToken(): Promise<string | null> {
  if (!refreshFlight) {
    refreshFlight = axios
      .post<Session>(
        `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/auth/refresh`,
        {},
        { withCredentials: true },
      )
      .then((response) => {
        setAccessToken(response.data.access)
        return response.data.access
      })
      .catch(() => {
        clearSession()
        return null
      })
      .finally(() => {
        refreshFlight = null
      })
  }
  return refreshFlight
}

function isAuthPath(url?: string) {
  return AUTH_PATHS.some((path) => url?.includes(path))
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !isAuthPath(original.url)
    ) {
      original._retried = true
      const token = await refreshAccessToken()
      if (token) {
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      }
    }

    const payload = error.response?.data?.error
    throw new ApiError(
      payload?.message || error.message || 'The request failed.',
      payload?.code || 'request_failed',
      error.response?.status || 0,
      payload?.details,
    )
  },
)
