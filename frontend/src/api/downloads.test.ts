import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  downloadBlobFromApiPath,
  filenameFromContentDisposition,
} from './downloads'

describe('downloads', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('decodes an RFC 5987 filename', () => {
    expect(
      filenameFromContentDisposition(
        "attachment; filename*=UTF-8''report%20final.pdf",
      ),
    ).toBe('report final.pdf')
  })

  it('rejects malformed encoded filenames safely', () => {
    expect(
      filenameFromContentDisposition(
        "attachment; filename*=UTF-8''report%ZZ.pdf",
      ),
    ).toBeNull()
  })

  it('rejects external download URLs before fetch', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      downloadBlobFromApiPath('https://evil.test/steal', 'fallback.bin'),
    ).rejects.toBeDefined()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
