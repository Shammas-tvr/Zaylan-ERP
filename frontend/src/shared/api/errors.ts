import axios from 'axios'

export class ApiError extends Error {
  status: number
  code: string
  details?: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { error?: { code?: string; message?: string; details?: unknown } }
      | undefined
    if (!error.response) {
      return new ApiError(0, 'network', 'Cannot reach the Zaylan API. Check that the backend is running.')
    }
    return new ApiError(
      error.response.status,
      data?.error?.code ?? 'error',
      data?.error?.message ?? 'The request could not be completed.',
      data?.error?.details,
    )
  }
  return new ApiError(0, 'error', 'Something went wrong. Please try again.')
}

export function errorMessage(error: unknown) {
  const apiError = toApiError(error)
  const details = formatDetails(apiError.details)
  if (details) return `${apiError.message} ${details}`.trim()
  return apiError.message
}

function formatDetails(details: unknown): string {
  if (!details || typeof details !== 'object') return ''
  const parts: string[] = []
  for (const [field, value] of Object.entries(details as Record<string, unknown>)) {
    if (field === 'non_field_errors') {
      parts.push(Array.isArray(value) ? value.map(String).join(' ') : String(value))
      continue
    }
    const text = Array.isArray(value) ? value.map(String).join(' ') : String(value)
    parts.push(`${field}: ${text}`)
  }
  return parts.join(' ')
}
