import type { ZodSchema } from 'zod'

import { toAbsoluteApiUrl } from '../shared/lib'
import { apiConfig } from './config'
import { parseApiError } from './errors'
import {
  emailDetailSchema,
  emailListResponseSchema,
  healthResponseSchema,
  statisticsResponseSchema,
} from './schemas'
import type {
  EmailDetail,
  EmailListParams,
  EmailListResponse,
  HealthResponse,
  StatisticsParams,
  StatisticsResponse,
} from './types'

const defaultJsonHeaders = {
  Accept: 'application/json',
}

function buildApiUrl(
  path: string,
  params?: Record<string, string | number | null | undefined>,
) {
  const url = new URL(path, apiConfig.baseUrl)

  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }

  return url.toString()
}

async function requestJson<T>(
  path: string,
  schema: ZodSchema<T>,
  options?: {
    params?: Record<string, string | number | null | undefined>
    signal?: AbortSignal
  },
): Promise<T> {
  const response = await fetch(buildApiUrl(path, options?.params), {
    headers: defaultJsonHeaders,
    signal: options?.signal,
  })

  if (!response.ok) {
    throw await parseApiError(response)
  }

  const data = await response.json()

  return schema.parse(data)
}

export function getHealthLive(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson('/health/live', healthResponseSchema, { signal })
}

export function getHealthReady(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson('/health/ready', healthResponseSchema, { signal })
}

export function getEmails(
  params: EmailListParams = {},
  signal?: AbortSignal,
): Promise<EmailListResponse> {
  return requestJson('/api/v1/emails', emailListResponseSchema, {
    params,
    signal,
  })
}

export function getStatistics(
  params: StatisticsParams,
  signal?: AbortSignal,
): Promise<StatisticsResponse> {
  return requestJson('/api/v1/statistics', statisticsResponseSchema, {
    params,
    signal,
  })
}

export function getEmail(
  recordId: string,
  signal?: AbortSignal,
): Promise<EmailDetail> {
  return requestJson(
    `/api/v1/emails/${encodeURIComponent(recordId)}`,
    emailDetailSchema,
    { signal },
  )
}

export function getAbsoluteApiUrl(path: string): string {
  return toAbsoluteApiUrl(path, apiConfig.baseUrl)
}
