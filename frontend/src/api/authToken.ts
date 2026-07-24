const authTokenStorageKey = 'mail-agent.access-token'
type AuthTokenListener = (token: string | null) => void

const authTokenListeners = new Set<AuthTokenListener>()

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
  notifyAuthTokenListeners(token)
}

export function clearStoredAuthToken(): void {
  getLocalStorage()?.removeItem(authTokenStorageKey)
  notifyAuthTokenListeners(null)
}

export function getBearerAuthorizationHeader(): string | null {
  const token = getStoredAuthToken()

  return token ? `Bearer ${token}` : null
}

export function subscribeToAuthTokenChanges(
  listener: AuthTokenListener,
): () => void {
  authTokenListeners.add(listener)

  function handleStorage(event: StorageEvent) {
    if (event.key === authTokenStorageKey) {
      listener(event.newValue)
    }
  }

  window.addEventListener('storage', handleStorage)

  return () => {
    authTokenListeners.delete(listener)
    window.removeEventListener('storage', handleStorage)
  }
}

function notifyAuthTokenListeners(token: string | null): void {
  for (const listener of authTokenListeners) {
    listener(token)
  }
}
