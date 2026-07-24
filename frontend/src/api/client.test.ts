import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getStoredAuthToken, setStoredAuthToken } from './authToken'
import { getEmails, login } from './client'

describe('API auth failures', () => {
  const values = new Map<string, string>()

  beforeEach(() => {
    values.clear()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => values.get(key) ?? null,
        removeItem: (key: string) => {
          values.delete(key)
        },
        setItem: (key: string, value: string) => {
          values.set(key, value)
        },
      },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('clears an expired token after authenticated 401 response', async () => {
    setStoredAuthToken('expired-token')
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { error: 'unauthorized', request_id: 'request-test' },
            { status: 401 },
          ),
        ),
    )

    await expect(getEmails()).rejects.toMatchObject({ status: 401 })
    expect(getStoredAuthToken()).toBeNull()
  })

  it('keeps an existing token after public login rejection', async () => {
    setStoredAuthToken('existing-token')
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { error: 'unauthorized', request_id: 'request-test' },
            { status: 401 },
          ),
        ),
    )

    await expect(
      login({ password: 'wrong', username: 'user' }),
    ).rejects.toMatchObject({ status: 401 })
    expect(getStoredAuthToken()).toBe('existing-token')
  })

  it('rejects invalid list parameters before fetch', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(getEmails({ limit: 101 })).rejects.toBeDefined()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
