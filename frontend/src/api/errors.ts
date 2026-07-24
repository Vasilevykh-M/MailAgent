import { apiErrorSchema } from './schemas'
import type { ApiErrorResponse } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly response: ApiErrorResponse | null

  constructor(status: number, response: ApiErrorResponse | null) {
    super(response?.error ?? `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.response = response
  }
}

export async function parseApiError(response: Response) {
  const data = await response.json().catch(() => null)
  const parsed = apiErrorSchema.safeParse(data)

  return new ApiError(response.status, parsed.success ? parsed.data : null)
}

export function shouldRetryApiRequest(
  failureCount: number,
  error: unknown,
): boolean {
  if (failureCount >= 1) {
    return false
  }

  if (error instanceof ApiError) {
    return error.status >= 500
  }

  return error instanceof TypeError
}
