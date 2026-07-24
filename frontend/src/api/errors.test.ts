import { describe, expect, it } from 'vitest'

import { ApiError, parseApiError, shouldRetryApiRequest } from './errors'

describe('parseApiError', () => {
  it('preserves safe API error payloads', async () => {
    const error = await parseApiError(
      Response.json(
        { error: 'unauthorized', request_id: 'request-test' },
        { status: 401 },
      ),
    )

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(401)
    expect(error.response?.request_id).toBe('request-test')
  })

  it('falls back when response body is not an API error', async () => {
    const error = await parseApiError(new Response('not-json', { status: 500 }))

    expect(error.message).toBe('HTTP 500')
    expect(error.response).toBeNull()
  })
})

describe('shouldRetryApiRequest', () => {
  it('retries one network or server failure', () => {
    expect(shouldRetryApiRequest(0, new TypeError('fetch failed'))).toBe(true)
    expect(shouldRetryApiRequest(0, new ApiError(503, null))).toBe(true)
    expect(shouldRetryApiRequest(1, new ApiError(503, null))).toBe(false)
  })

  it('does not retry client or validation failures', () => {
    expect(shouldRetryApiRequest(0, new ApiError(401, null))).toBe(false)
    expect(shouldRetryApiRequest(0, new ApiError(422, null))).toBe(false)
    expect(shouldRetryApiRequest(0, new Error('invalid response'))).toBe(false)
  })
})
