import { describe, expect, it } from 'vitest'

import { resolveApiBaseUrl } from './config'

describe('resolveApiBaseUrl', () => {
  it('uses configured API base URL in dev mode', () => {
    expect(
      resolveApiBaseUrl(
        {
          DEV: true,
          VITE_RESULTS_API_BASE_URL: 'http://127.0.0.1:8080',
        },
        {
          protocol: 'https:',
          hostname: 'frontend.example.com',
        },
      ),
    ).toBe('http://127.0.0.1:8080')
  })

  it('uses frontend host with API port in preview and production builds', () => {
    expect(
      resolveApiBaseUrl(
        {
          DEV: false,
          VITE_RESULTS_API_BASE_URL: 'http://127.0.0.1:8080',
        },
        {
          protocol: 'https:',
          hostname: 'dashboard.example.com',
        },
      ),
    ).toBe('https://dashboard.example.com:8080')
  })

  it('does not reuse frontend port in preview and production builds', () => {
    expect(
      resolveApiBaseUrl(
        {
          DEV: false,
        },
        {
          protocol: 'http:',
          hostname: '192.168.88.32',
        },
      ),
    ).toBe('http://192.168.88.32:8080')
  })
})
