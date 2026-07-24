import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDebouncedValue } from './useDebouncedValue'

describe('useDebouncedValue', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('updates only after the configured delay', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: 'INBOX' } },
    )

    rerender({ value: 'ARCHIVE' })
    expect(result.current).toBe('INBOX')

    act(() => {
      vi.advanceTimersByTime(299)
    })
    expect(result.current).toBe('INBOX')

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(result.current).toBe('ARCHIVE')
  })
})
