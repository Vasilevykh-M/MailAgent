import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  queryKeys,
  useEmailDetail,
  useEmailsInfinite,
  useStatistics,
  type EmailDetail,
  type EmailListItem,
} from '../../../api'
import { apiConfig } from '../../../api/config'
import {
  dateInputToIsoNextDay,
  dateInputToIsoStart,
  formatDateForInput,
} from '../../../shared'
import { Badge } from '../../../shared'
import {
  DashboardFilters,
  type DashboardFiltersValue,
} from '../DashboardFilters'
import { EmailDetailPanel } from '../EmailDetailPanel'
import { EmailList } from '../EmailList'
import { HealthIndicator } from '../HealthIndicator'
import { StatisticsCards } from '../StatisticsCards'
import { StatisticsCharts } from '../StatisticsCharts'

import styles from './DashboardPage.module.css'

const emailPageLimit = 10

function defaultFilters(): DashboardFiltersValue {
  const today = new Date()
  const monthStart = new Date(today)

  monthStart.setDate(1)

  return {
    fromDate: formatDateForInput(monthStart),
    toDate: formatDateForInput(today),
    mailbox: apiConfig.defaultMailbox,
    search: '',
    attachmentFilter: 'all',
    confidenceFilter: 'all',
    statusFilter: 'all',
  }
}

function matchesSearch(item: EmailListItem, search: string) {
  const normalizedSearch = search.trim().toLowerCase()

  if (!normalizedSearch) {
    return true
  }

  return [item.subject, item.from, item.summary_preview]
    .join(' ')
    .toLowerCase()
    .includes(normalizedSearch)
}

function matchesAttachmentFilter(
  item: EmailListItem,
  filter: DashboardFiltersValue['attachmentFilter'],
) {
  if (filter === 'with') {
    return item.attachment_count > 0
  }

  if (filter === 'without') {
    return item.attachment_count === 0
  }

  return true
}

function matchesConfidenceFilter(
  item: EmailListItem,
  filter: DashboardFiltersValue['confidenceFilter'],
) {
  if (filter === 'none') {
    return item.confidence === null
  }

  if (filter === 'high') {
    return typeof item.confidence === 'number' && item.confidence >= 0.8
  }

  if (filter === 'medium') {
    return (
      typeof item.confidence === 'number' &&
      item.confidence >= 0.5 &&
      item.confidence < 0.8
    )
  }

  if (filter === 'low') {
    return typeof item.confidence === 'number' && item.confidence < 0.5
  }

  return true
}

function matchesStatusFilter(
  detail: EmailDetail | undefined,
  filter: DashboardFiltersValue['statusFilter'],
) {
  if (filter === 'all') {
    return true
  }

  if (filter === 'uncached') {
    return !detail
  }

  return detail?.classification?.status === filter
}

export function DashboardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { recordId = null } = useParams()
  const detailPanelRef = useRef<HTMLDivElement | null>(null)
  const [filters, setFilters] = useState(defaultFilters)
  const apiParams = useMemo(
    () => ({
      from: dateInputToIsoStart(filters.fromDate),
      to: dateInputToIsoNextDay(filters.toDate),
      mailbox: filters.mailbox.trim() || null,
      limit: emailPageLimit,
    }),
    [filters.fromDate, filters.mailbox, filters.toDate],
  )
  const statistics = useStatistics({
    from: apiParams.from,
    to: apiParams.to,
    mailbox: apiParams.mailbox,
  })
  const emails = useEmailsInfinite(apiParams)
  const { fetchNextPage } = emails
  const emailDetail = useEmailDetail(recordId)
  const emailItems =
    emails.data?.pages
      .flatMap((page) => page.items)
      .filter((item) => matchesSearch(item, filters.search))
      .filter((item) => matchesAttachmentFilter(item, filters.attachmentFilter))
      .filter((item) => matchesConfidenceFilter(item, filters.confidenceFilter))
      .filter((item) =>
        matchesStatusFilter(
          queryClient.getQueryData<EmailDetail>(
            queryKeys.emails.detail(item.id),
          ),
          filters.statusFilter,
        ),
      ) ?? []
  const nextEmailCursor =
    emails.data?.pages[emails.data.pages.length - 1]?.next_cursor ?? null
  function selectEmail(selectedRecordId: string) {
    navigate(`/emails/${selectedRecordId}`)
  }

  const loadMoreEmails = useCallback(() => {
    void fetchNextPage()
  }, [fetchNextPage])

  useEffect(() => {
    if (!recordId) {
      return
    }

    window.requestAnimationFrame(() => {
      detailPanelRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    })
  }, [recordId])

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.hero}>
          <div className={styles.headerRow}>
            <p className={styles.eyebrow}>Mail Agent</p>
            <div className={styles.statusGroup}>
              <HealthIndicator />
              <Badge tone="accent">Dashboard</Badge>
            </div>
          </div>
          <div className={styles.heroContent}>
            <div>
              <h1 className={styles.title}>Dashboard обработанных писем</h1>
              <p className={styles.description}>
                Просмотр обработанных писем, сводок, классификации, вложений и
                статистики за выбранный период.
              </p>
            </div>
            <div className={styles.configCard}>
              <div>
                API: <span>{apiConfig.baseUrl}</span>
              </div>
              <div>
                Mailbox: <span>{apiConfig.defaultMailbox}</span>
              </div>
            </div>
          </div>
        </header>

        <DashboardFilters onChange={setFilters} value={filters} />

        <StatisticsCards
          data={statistics.data}
          isError={statistics.isError}
          isLoading={statistics.isLoading}
        />

        <StatisticsCharts
          data={statistics.data}
          isError={statistics.isError}
          isLoading={statistics.isLoading}
        />

        <div className={styles.contentGrid}>
          <EmailList
            hasNextPage={emails.hasNextPage}
            isError={emails.isError}
            isFetchingNextPage={emails.isFetchingNextPage}
            isLoading={emails.isLoading}
            items={emailItems}
            nextCursor={nextEmailCursor}
            onLoadMore={loadMoreEmails}
            onSelect={selectEmail}
            selectedId={recordId}
          />
          <div className={styles.detailPanelAnchor} ref={detailPanelRef}>
            <EmailDetailPanel
              data={emailDetail.data}
              isError={emailDetail.isError}
              isLoading={emailDetail.isLoading}
              isPlaceholder={!recordId}
            />
          </div>
        </div>
      </div>
    </main>
  )
}
