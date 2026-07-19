import { describe, expect, it } from 'vitest'

import { emailListResponseSchema, statisticsResponseSchema } from './schemas'

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
})
