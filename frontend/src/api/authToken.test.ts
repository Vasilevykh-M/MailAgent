import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  clearStoredAuthToken,
  getBearerAuthorizationHeader,
  getStoredAuthToken,
  setStoredAuthToken,
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
})
