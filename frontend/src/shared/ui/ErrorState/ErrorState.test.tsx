import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ErrorState } from './ErrorState'

describe('ErrorState', () => {
  afterEach(cleanup)

  it('announces details and exposes retry action', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()

    render(
      <ErrorState
        description="Не удалось загрузить данные."
        details="request_id: request-test"
        onRetry={onRetry}
        title="Ошибка"
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('request-test')
    await user.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
