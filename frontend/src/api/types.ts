import type { z } from 'zod'

import type {
  apiErrorSchema,
  attachmentSchema,
  classificationSchema,
  classificationStatisticsItemSchema,
  currentUserSchema,
  emailDetailSchema,
  emailListItemSchema,
  emailListResponseSchema,
  healthResponseSchema,
  loginResponseSchema,
  originalEmailSchema,
  statisticsResponseSchema,
} from './schemas'

export type ApiErrorResponse = z.infer<typeof apiErrorSchema>
export type AuthUser = z.infer<typeof currentUserSchema>
export type LoginResponse = z.infer<typeof loginResponseSchema>
export type HealthResponse = z.infer<typeof healthResponseSchema>
export type Classification = z.infer<typeof classificationSchema>
export type EmailListItem = z.infer<typeof emailListItemSchema>
export type EmailListResponse = z.infer<typeof emailListResponseSchema>
export type StatisticsResponse = z.infer<typeof statisticsResponseSchema>
export type ClassificationStatisticsItem = z.infer<
  typeof classificationStatisticsItemSchema
>
export type OriginalEmail = z.infer<typeof originalEmailSchema>
export type Attachment = z.infer<typeof attachmentSchema>
export type EmailDetail = z.infer<typeof emailDetailSchema>

export type EmailListParams = {
  limit?: number
  cursor?: string | null
  from?: string | null
  to?: string | null
  mailbox?: string | null
}

export type StatisticsParams = {
  from: string | null
  to: string | null
  mailbox?: string | null
}

export type LoginPayload = {
  username: string
  password: string
}
