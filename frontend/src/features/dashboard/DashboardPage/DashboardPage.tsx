import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  useEmailDetail,
  useEmailsInfinite,
  useStatistics,
  type EmailListItem,
} from '../../../api'
import { apiConfig } from '../../../api/config'
import {
  dateInputToIsoNextDay,
  dateInputToIsoStart,
  formatDateForInput,
} from '../../../shared'
import { Alert, Badge } from '../../../shared'
import {
  DashboardFilters,
  type DashboardFiltersValue,
} from '../DashboardFilters'
import { EmailDetailPanel } from '../EmailDetailPanel'
import { EmailList } from '../EmailList'
import { HealthIndicator } from '../HealthIndicator'
import { StatisticsCards } from '../StatisticsCards'

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

export function DashboardPage() {
  const navigate = useNavigate()
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
  const emailItems = useMemo(
    () =>
      emails.data?.pages
        .flatMap((page) => page.items)
        .filter((item) => matchesSearch(item, filters.search)) ?? [],
    [emails.data?.pages, filters.search],
  )
  const nextEmailCursor =
    emails.data?.pages[emails.data.pages.length - 1]?.next_cursor ?? null
  const isRefreshing = statistics.isFetching || emails.isFetching

  function refreshDashboard() {
    void statistics.refetch()
    void emails.refetch()
    if (recordId) {
      void emailDetail.refetch()
    }
  }

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
              <Badge tone="accent">MSW в dev</Badge>
            </div>
          </div>
          <div className={styles.heroContent}>
            <div>
              <h1 className={styles.title}>Dashboard обработанных писем</h1>
              <p className={styles.description}>
                Первый рабочий слой dashboard: состояние API, фильтры периода,
                KPI и список обработанных писем. Detail panel будет подключён
                отдельным шагом.
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

        <Alert title="Локальные ограничения MVP" tone="info">
          Поиск применяется только к уже загруженным страницам. API пока не даёт
          server-side поиск, фильтр по классу и список mailbox.
        </Alert>

        <DashboardFilters
          isRefreshing={isRefreshing}
          onChange={setFilters}
          onRefresh={refreshDashboard}
          value={filters}
        />

        <StatisticsCards
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
