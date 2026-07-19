const DEFAULT_API_BASE_URL = 'http://192.168.88.32:8080'
const DEFAULT_MAILBOX = 'INBOX'

export const apiConfig = {
  baseUrl: import.meta.env.VITE_RESULTS_API_BASE_URL || DEFAULT_API_BASE_URL,
  defaultMailbox: import.meta.env.VITE_DEFAULT_MAILBOX || DEFAULT_MAILBOX,
}
