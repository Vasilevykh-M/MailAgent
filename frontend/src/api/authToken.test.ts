import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearStoredAuthToken,
  getBearerAuthorizationHeader,
  getStoredAuthToken,
  setStoredAuthToken,
  subscribeToAuthTokenChanges,
} from './authToken'

describe('authToken', () => {
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
    clearStoredAuthToken()
  })

  it('stores token and builds Bearer Authorization header', () => {
    setStoredAuthToken('token-value')

    expect(getStoredAuthToken()).toBe('token-value')
    expect(getBearerAuthorizationHeader()).toBe('Bearer token-value')
  })

  it('returns null authorization header without token', () => {
    expect(getBearerAuthorizationHeader()).toBeNull()
  })

  it('notifies subscribers when current-tab token changes', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeToAuthTokenChanges(listener)

    setStoredAuthToken('token-value')
    clearStoredAuthToken()

    expect(listener).toHaveBeenNthCalledWith(1, 'token-value')
    expect(listener).toHaveBeenNthCalledWith(2, null)

    unsubscribe()
  })
})
