import type { ZodSchema } from 'zod'

import { toAbsoluteApiUrl } from '../shared/lib'
import { getBearerAuthorizationHeader } from './authToken'
import { apiConfig } from './config'
import { parseApiError } from './errors'
import {
  currentUserSchema,
  emailDetailSchema,
  emailListResponseSchema,
  healthResponseSchema,
  loginResponseSchema,
  statisticsResponseSchema,
} from './schemas'
import type {
  AuthUser,
  EmailDetail,
  EmailListParams,
  EmailListResponse,
  HealthResponse,
  LoginPayload,
  LoginResponse,
  StatisticsParams,
  StatisticsResponse,
} from './types'

type ApiHeadersOptions = {
  acceptJson?: boolean
  contentTypeJson?: boolean
  includeAuth?: boolean
}

export function buildApiHeaders({
  acceptJson = true,
  contentTypeJson = false,
  includeAuth = true,
}: ApiHeadersOptions = {}): Headers {
  const headers = new Headers()

  if (acceptJson) {
    headers.set('Accept', 'application/json')
  }

  if (contentTypeJson) {
    headers.set('Content-Type', 'application/json')
  }

  const authorization = includeAuth ? getBearerAuthorizationHeader() : null

  if (authorization) {
    headers.set('Authorization', authorization)
  }

  return headers
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
    body?: unknown
    includeAuth?: boolean
    method?: 'GET' | 'POST'
    params?: Record<string, string | number | null | undefined>
    signal?: AbortSignal
  },
): Promise<T> {
  const response = await fetch(buildApiUrl(path, options?.params), {
    body:
      options?.body === undefined ? undefined : JSON.stringify(options.body),
    headers: buildApiHeaders({
      contentTypeJson: options?.body !== undefined,
      includeAuth: options?.includeAuth,
    }),
    method: options?.method ?? 'GET',
    signal: options?.signal,
  })

  if (!response.ok) {
    throw await parseApiError(response)
  }

  const data = await response.json()

  return schema.parse(data)
}

async function requestNoContent(
  path: string,
  options?: {
    method?: 'POST'
    signal?: AbortSignal
  },
): Promise<void> {
  const response = await fetch(buildApiUrl(path), {
    headers: buildApiHeaders(),
    method: options?.method ?? 'POST',
    signal: options?.signal,
  })

  if (!response.ok) {
    throw await parseApiError(response)
  }
}

export function login(
  payload: LoginPayload,
  signal?: AbortSignal,
): Promise<LoginResponse> {
  return requestJson('/api/v1/auth/login', loginResponseSchema, {
    body: payload,
    includeAuth: false,
    method: 'POST',
    signal,
  })
}

export function getCurrentUser(signal?: AbortSignal): Promise<AuthUser> {
  return requestJson('/api/v1/auth/me', currentUserSchema, { signal })
}

export function logout(signal?: AbortSignal): Promise<void> {
  return requestNoContent('/api/v1/auth/logout', {
    method: 'POST',
    signal,
  })
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
