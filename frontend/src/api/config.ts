const DEFAULT_DEV_API_BASE_URL = 'http://192.168.88.32:8080'
const DEFAULT_API_PORT = '8080'
const DEFAULT_MAILBOX = 'INBOX'

type ApiRuntimeEnv = {
  DEV: boolean
  VITE_RESULTS_API_BASE_URL?: string
}

type ApiLocation = Pick<Location, 'hostname' | 'protocol'>

export function resolveApiBaseUrl(
  env: ApiRuntimeEnv = import.meta.env,
  location: ApiLocation = globalThis.location,
): string {
  if (env.DEV) {
    return env.VITE_RESULTS_API_BASE_URL || DEFAULT_DEV_API_BASE_URL
  }

  return `${location.protocol}//${location.hostname}:${DEFAULT_API_PORT}`
}

export const apiConfig = {
  baseUrl: resolveApiBaseUrl(),
  defaultMailbox: import.meta.env.VITE_DEFAULT_MAILBOX || DEFAULT_MAILBOX,
}
