import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../../shared'
import { LoginPage } from './LoginPage'

const authMock = vi.hoisted(() => ({
  login: vi.fn(async (): Promise<void> => undefined),
  logout: vi.fn(async (): Promise<void> => undefined),
  status: 'anonymous' as const,
  user: null,
}))

vi.mock('./useAuth', () => ({
  useAuth: () => authMock,
}))

describe('LoginPage', () => {
  beforeEach(() => {
    const values = new Map<string, string>()

    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => {
          values.set(key, value)
        },
      },
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('shows field errors and does not submit blank credentials', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <ThemeProvider>
          <LoginPage />
        </ThemeProvider>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Войти' }))

    expect(screen.getByText('Введите username.')).toBeInTheDocument()
    expect(screen.getByText('Введите password.')).toBeInTheDocument()
    expect(authMock.login).not.toHaveBeenCalled()
  })
})
