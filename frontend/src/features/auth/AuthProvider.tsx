import type { ReactNode } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  clearStoredAuthToken,
  getCurrentUser,
  getStoredAuthToken,
  login as loginRequest,
  logout as logoutRequest,
  setStoredAuthToken,
  type AuthUser,
  type LoginPayload,
} from '../../api'
import { AuthContext, type AuthStatus } from './context'

type AuthProviderProps = {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [status, setStatus] = useState<AuthStatus>(() =>
    getStoredAuthToken() ? 'checking' : 'anonymous',
  )
  const [user, setUser] = useState<AuthUser | null>(null)

  useEffect(() => {
    const token = getStoredAuthToken()

    if (!token) {
      setStatus('anonymous')
      setUser(null)
      return
    }

    const controller = new AbortController()
    setStatus('checking')

    getCurrentUser(controller.signal)
      .then((currentUser) => {
        setUser(currentUser)
        setStatus('authenticated')
      })
      .catch(() => {
        clearStoredAuthToken()
        setUser(null)
        setStatus('anonymous')
      })

    return () => {
      controller.abort()
    }
  }, [])

  const login = useCallback(async (payload: LoginPayload) => {
    const response = await loginRequest(payload)

    setStoredAuthToken(response.access_token)
    setUser(response.user)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    try {
      if (getStoredAuthToken()) {
        await logoutRequest()
      }
    } finally {
      clearStoredAuthToken()
      setUser(null)
      setStatus('anonymous')
    }
  }, [])

  const value = useMemo(
    () => ({
      login,
      logout,
      status,
      user,
    }),
    [login, logout, status, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
