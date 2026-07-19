import type { EmailListParams, StatisticsParams } from './types'

export const queryKeys = {
  health: {
    live: ['health', 'live'] as const,
    ready: ['health', 'ready'] as const,
  },
  emails: {
    list: (params: Omit<EmailListParams, 'cursor'>) =>
      ['emails', 'list', params] as const,
    detail: (recordId: string) => ['emails', 'detail', recordId] as const,
  },
  statistics: {
    detail: (params: StatisticsParams) => ['statistics', params] as const,
  },
}
