import { describe, expect, it } from 'vitest'

import { toAbsoluteApiUrl } from './url'

describe('toAbsoluteApiUrl', () => {
  it('converts relative API paths to absolute URLs', () => {
    expect(
      toAbsoluteApiUrl('/api/v1/emails/abc/raw', 'http://192.168.88.32:8080'),
    ).toBe('http://192.168.88.32:8080/api/v1/emails/abc/raw')
  })

  it('keeps already absolute URLs valid against the base URL', () => {
    expect(
      toAbsoluteApiUrl(
        'http://127.0.0.1:8080/api/v1/emails',
        'http://192.168.88.32:8080',
      ),
    ).toBe('http://127.0.0.1:8080/api/v1/emails')
  })
})
