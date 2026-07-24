import { describe, expect, it } from 'vitest'

import {
  apiDownloadPathSchema,
  emailListParamsSchema,
  emailListResponseSchema,
  loginPayloadSchema,
  statisticsParamsSchema,
  statisticsResponseSchema,
} from './schemas'

describe('api schemas', () => {
  it('parses email list responses from Results API', () => {
    const parsed = emailListResponseSchema.parse({
      items: [
        {
          record_id: 'a'.repeat(64),
          id: 'a'.repeat(64),
          received_at: '2026-07-17T10:00:00Z',
          from: 'sender@example.test',
          subject: 'Тема',
          summary_preview: 'Кратко',
          attachment_count: 1,
          confidence: 0.9,
        },
      ],
      next_cursor: null,
      has_more: false,
    })

    expect(parsed.items[0]?.subject).toBe('Тема')
  })

  it('parses nullable classification statistics fields', () => {
    const parsed = statisticsResponseSchema.parse({
      from: '2026-07-01T00:00:00Z',
      to: '2026-08-01T00:00:00Z',
      mailbox: 'INBOX',
      total_emails: 3,
      total_attachments: 0,
      classifications: [
        {
          status: 'new_project',
          class_code: null,
          class_name_ru: null,
          count: 3,
        },
      ],
    })

    expect(parsed.classifications[0]?.class_code).toBeNull()
  })

  it('rejects confidence outside the supported range', () => {
    expect(() =>
      emailListResponseSchema.parse({
        items: [
          {
            record_id: 'record-id',
            id: 'record-id',
            received_at: '2026-07-17T10:00:00Z',
            from: 'sender@example.test',
            subject: 'Тема',
            summary_preview: 'Кратко',
            attachment_count: 1,
            confidence: 1.1,
          },
        ],
        next_cursor: null,
        has_more: false,
      }),
    ).toThrow()
  })

  it('requires a cursor when another page exists', () => {
    expect(() =>
      emailListResponseSchema.parse({
        items: [],
        next_cursor: null,
        has_more: true,
      }),
    ).toThrow()
  })

  it('validates API query parameters and date order', () => {
    expect(
      emailListParamsSchema.safeParse({
        from: '2026-07-02T00:00:00Z',
        limit: 101,
        to: '2026-07-01T00:00:00Z',
      }).success,
    ).toBe(false)
    expect(
      statisticsParamsSchema.safeParse({
        from: 'not-a-date',
        to: '2026-07-01T00:00:00Z',
      }).success,
    ).toBe(false)
  })

  it('normalizes login username and rejects blank credentials', () => {
    expect(
      loginPayloadSchema.parse({ password: 'secret', username: ' user ' }),
    ).toEqual({ password: 'secret', username: 'user' })
    expect(
      loginPayloadSchema.safeParse({ password: '', username: '   ' }).success,
    ).toBe(false)
  })

  it('accepts only relative email download paths', () => {
    expect(
      apiDownloadPathSchema.safeParse(
        '/api/v1/emails/record-id/attachments/file-id/content',
      ).success,
    ).toBe(true)
    expect(
      apiDownloadPathSchema.safeParse('https://evil.test/steal').success,
    ).toBe(false)
    expect(
      apiDownloadPathSchema.safeParse(
        '/api/v1/emails/record-id/../../auth/logout',
      ).success,
    ).toBe(false)
  })
})
