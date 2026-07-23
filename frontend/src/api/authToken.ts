const authTokenStorageKey = 'mail-agent.access-token'

function getLocalStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

export function getStoredAuthToken(): string | null {
  return getLocalStorage()?.getItem(authTokenStorageKey) ?? null
}

export function setStoredAuthToken(token: string): void {
  getLocalStorage()?.setItem(authTokenStorageKey, token)
}

export function clearStoredAuthToken(): void {
  getLocalStorage()?.removeItem(authTokenStorageKey)
}

export function getBearerAuthorizationHeader(): string | null {
  const token = getStoredAuthToken()

  return token ? `Bearer ${token}` : null
}
