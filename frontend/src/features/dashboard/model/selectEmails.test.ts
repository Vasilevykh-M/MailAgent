import { describe, expect, it } from 'vitest'

import type { EmailListItem } from '../../../api'
import { getClassificationClassLabel } from './classification'
import type { DashboardFiltersValue } from './filters'
import { selectVisibleEmails } from './selectEmails'

const items: EmailListItem[] = [
  {
    attachment_count: 1,
    class_code: null,
    class_name_ru: null,
    confidence: 0.9,
    from: 'sales@example.test',
    id: 'mail-1',
    received_at: '2026-07-17T10:00:00Z',
    record_id: 'mail-1',
    subject: 'Коммерческое предложение',
    summary_preview: 'Поставка станка',
  },
  {
    attachment_count: 0,
    class_code: null,
    class_name_ru: null,
    confidence: null,
    from: 'info@example.test',
    id: 'mail-2',
    received_at: '2026-07-18T10:00:00Z',
    record_id: 'mail-2',
    subject: 'Общий вопрос',
    summary_preview: 'Без вложений',
  },
]

function createFilters(
  overrides: Partial<DashboardFiltersValue> = {},
): DashboardFiltersValue {
  return {
    attachmentFilter: [],
    classFilter: [],
    fromDate: '2026-07-01',
    mailbox: 'INBOX',
    statusFilter: [],
    toDate: '2026-07-31',
    ...overrides,
  }
}

describe('selectVisibleEmails', () => {
  it('filters loaded items by search and attachments', () => {
    const result = selectVisibleEmails({
      detailsById: new Map(),
      filters: createFilters({ attachmentFilter: ['with'] }),
      items,
      search: 'станка',
    })

    expect(result.map((item) => item.id)).toEqual(['mail-1'])
  })

  it('enriches classification from cached detail before filtering', () => {
    const result = selectVisibleEmails({
      detailsById: new Map([
        [
          'mail-1',
          {
            classification: {
              class_code: 'MACHINES',
              class_name_ru: 'Станки',
              status: 'manual_review',
            },
          },
        ],
      ]),
      filters: createFilters({
        classFilter: ['MACHINES'],
        statusFilter: ['manual_review'],
      }),
      items,
      search: '',
    })

    expect(result).toHaveLength(1)
    expect(result[0]?.class_name_ru).toBe('Станки')
  })

  it('supports the explicit uncached status filter', () => {
    const result = selectVisibleEmails({
      detailsById: new Map([
        ['mail-1', { classification: { status: 'classified' } }],
      ]),
      filters: createFilters({ statusFilter: ['uncached'] }),
      items,
      search: '',
    })

    expect(result.map((item) => item.id)).toEqual(['mail-2'])
  })
})

describe('classification model', () => {
  it('uses one label source with safe fallback', () => {
    expect(getClassificationClassLabel('MACHINES', null)).toBe('Станки')
    expect(getClassificationClassLabel('FUTURE_CLASS', null)).toBe(
      'FUTURE_CLASS',
    )
    expect(getClassificationClassLabel(null, null)).toBe('Без класса')
  })
})
