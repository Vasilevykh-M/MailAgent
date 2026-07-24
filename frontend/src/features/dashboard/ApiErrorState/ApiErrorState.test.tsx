import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '../../../api'
import { ApiErrorState } from './ApiErrorState'

describe('ApiErrorState', () => {
  afterEach(cleanup)

  it('shows a safe request identifier without exposing the response body', () => {
    render(
      <ApiErrorState
        description="Не удалось загрузить данные."
        error={
          new ApiError(503, {
            error: 'storage_unavailable',
            request_id: 'request-test',
          })
        }
        title="Ошибка API"
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'request_id: request-test',
    )
  })
})
