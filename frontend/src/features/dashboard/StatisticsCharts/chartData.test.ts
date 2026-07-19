import { describe, expect, it } from 'vitest'

import type { StatisticsResponse } from '../../../api'
import { buildClassChartData, buildStatusChartData } from './chartData'

const statistics: StatisticsResponse = {
  from: '2026-07-01T00:00:00Z',
  to: '2026-08-01T00:00:00Z',
  mailbox: 'INBOX',
  total_emails: 6,
  total_attachments: 2,
  classifications: [
    {
      status: 'classified',
      class_code: 'MACHINES',
      class_name_ru: 'Станки',
      count: 2,
    },
    {
      status: 'classified',
      class_code: 'ROBOTIC_CELLS',
      class_name_ru: 'Роботизированные ячейки',
      count: 1,
    },
    {
      status: 'new_project',
      class_code: null,
      class_name_ru: null,
      count: 3,
    },
  ],
}

describe('statistics chart data', () => {
  it('groups statistics by status', () => {
    expect(buildStatusChartData(statistics)).toMatchObject([
      { name: 'Классифицировано', value: 3 },
      { name: 'Новые проекты', value: 3 },
    ])
  })

  it('keeps only classified classes for class chart', () => {
    expect(buildClassChartData(statistics)).toMatchObject([
      { name: 'Станки', value: 2 },
      { name: 'Роботизированные ячейки', value: 1 },
    ])
  })
})
