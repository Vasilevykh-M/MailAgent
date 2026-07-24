import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  clearStoredAuthToken: vi.fn(),
  getCurrentUser: vi.fn(async () => ({ id: 'user-id', username: 'user' })),
  getStoredAuthToken: vi.fn((): string | null => null),
  login: vi.fn(async () => ({
    access_token: 'token',
    expires_in: 3600,
    token_type: 'bearer' as const,
    user: { id: 'user-id', username: 'user' },
  })),
  logout: vi.fn(async (): Promise<void> => undefined),
  setStoredAuthToken: vi.fn(),
  subscribeToAuthTokenChanges: vi.fn(() => () => undefined),
}))

vi.mock('../../api', () => apiMocks)

import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'

function AuthProbe() {
  const auth = useAuth()
  const [outcome, setOutcome] = useState('idle')

  async function handleLogout() {
    try {
      await auth.logout()
      setOutcome('resolved')
    } catch {
      setOutcome('rejected')
    }
  }

  return (
    <>
      <span>{auth.status}</span>
      <span>{outcome}</span>
      <button onClick={() => void handleLogout()} type="button">
        Выйти
      </button>
    </>
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    apiMocks.getStoredAuthToken.mockReturnValue('stored-token')
    apiMocks.logout.mockRejectedValueOnce(new Error('API unavailable'))
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('finishes local logout when remote logout fails', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient()
    queryClient.setQueryData(['private-data'], { secret: true })

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AuthProbe />
        </AuthProvider>
      </QueryClientProvider>,
    )

    await screen.findByText('authenticated')
    await user.click(screen.getByRole('button', { name: 'Выйти' }))

    await waitFor(() => {
      expect(screen.getByText('resolved')).toBeInTheDocument()
    })
    expect(screen.getByText('anonymous')).toBeInTheDocument()
    expect(apiMocks.clearStoredAuthToken).toHaveBeenCalledOnce()
    expect(queryClient.getQueryData(['private-data'])).toBeUndefined()
  })
})
