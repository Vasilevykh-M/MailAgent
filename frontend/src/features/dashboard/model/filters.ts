import type {
  ClassificationClassCode,
  ClassificationStatus,
} from './classification'

export type AttachmentFilterValue = 'with' | 'without'
export type ClassFilterValue = ClassificationClassCode | 'none'
export type StatusFilterValue = ClassificationStatus | 'uncached'

export type DashboardFiltersValue = {
  fromDate: string
  toDate: string
  mailbox: string
  attachmentFilter: AttachmentFilterValue[]
  classFilter: ClassFilterValue[]
  statusFilter: StatusFilterValue[]
}

export const attachmentFilterOptions = [
  { label: 'С вложениями', value: 'with' },
  { label: 'Без вложений', value: 'without' },
] as const
