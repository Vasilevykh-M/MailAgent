import { createContext } from 'react'

import type { AuthUser, LoginPayload } from '../../api'

export type AuthStatus = 'checking' | 'authenticated' | 'anonymous'

export type AuthContextValue = {
  login: (payload: LoginPayload) => Promise<void>
  logout: () => Promise<void>
  status: AuthStatus
  user: AuthUser | null
}

export const AuthContext = createContext<AuthContextValue | null>(null)
