import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import {
  getEmail,
  getEmails,
  getHealthLive,
  getHealthReady,
  getStatistics,
} from './client'
import { queryKeys } from './queryKeys'
import { emailListParamsSchema, statisticsParamsSchema } from './schemas'
import type { EmailListParams, StatisticsParams } from './types'

export function useHealthLive() {
  return useQuery({
    queryKey: queryKeys.health.live,
    queryFn: ({ signal }) => getHealthLive(signal),
    refetchInterval: 30_000,
  })
}

export function useHealthReady() {
  return useQuery({
    queryKey: queryKeys.health.ready,
    queryFn: ({ signal }) => getHealthReady(signal),
    refetchInterval: 30_000,
  })
}

export function useStatistics(params: StatisticsParams, enabled = true) {
  const parsedParams = statisticsParamsSchema.safeParse(params)

  return useQuery({
    queryKey: queryKeys.statistics.detail(params),
    queryFn: ({ signal }) => getStatistics(params, signal),
    enabled:
      enabled &&
      parsedParams.success &&
      Boolean(parsedParams.data.from && parsedParams.data.to),
  })
}

export function useEmailsInfinite(
  params: Omit<EmailListParams, 'cursor'>,
  enabled = true,
) {
  const hasValidParams = emailListParamsSchema.safeParse(params).success

  return useInfiniteQuery({
    queryKey: queryKeys.emails.list(params),
    queryFn: ({ pageParam, signal }) =>
      getEmails({ ...params, cursor: pageParam }, signal),
    initialPageParam: null as string | null,
    enabled: enabled && hasValidParams,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_cursor : undefined,
  })
}

export function useEmailDetail(recordId: string | null) {
  return useQuery({
    queryKey: queryKeys.emails.detail(recordId ?? ''),
    queryFn: ({ signal }) => getEmail(recordId ?? '', signal),
    enabled: Boolean(recordId),
  })
}
