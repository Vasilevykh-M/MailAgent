import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  queryKeys,
  useEmailDetail,
  useEmailsInfinite,
  type EmailDetail,
  type EmailListItem,
} from '../../../api'
import { dateInputToIsoNextDay, dateInputToIsoStart } from '../../../shared'
import { Modal } from '../../../shared'
import {
  DashboardFilters,
  defaultFilters,
  type DashboardFiltersValue,
} from '../DashboardFilters'
import { EmailDetailPanel } from '../EmailDetailPanel'
import { EmailList } from '../EmailList'
import { HealthIndicator } from '../HealthIndicator'

import styles from './DashboardPage.module.css'

const emailPageLimit = 10

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
  if (filter.length === 0) {
    return true
  }

  return filter.some((filterValue) => {
    if (filterValue === 'with') {
      return item.attachment_count > 0
    }

    return item.attachment_count === 0
  })
}

function matchesConfidenceFilter(
  item: EmailListItem,
  filter: DashboardFiltersValue['confidenceFilter'],
) {
  if (filter.length === 0) {
    return true
  }

  return filter.some((filterValue) => {
    if (filterValue === 'none') {
      return item.confidence === null
    }

    if (filterValue === 'high') {
      return typeof item.confidence === 'number' && item.confidence >= 0.8
    }

    if (filterValue === 'medium') {
      return (
        typeof item.confidence === 'number' &&
        item.confidence >= 0.5 &&
        item.confidence < 0.8
      )
    }

    return typeof item.confidence === 'number' && item.confidence < 0.5
  })
}

function matchesStatusFilter(
  detail: EmailDetail | undefined,
  filter: DashboardFiltersValue['statusFilter'],
) {
  if (filter.length === 0) {
    return true
  }

  return filter.some((filterValue) => {
    if (filterValue === 'uncached') {
      return !detail
    }

    return detail?.classification?.status === filterValue
  })
}

export function DashboardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { recordId = null } = useParams()
  const [filters, setFilters] = useState(defaultFilters)
  const [search, setSearch] = useState('')
  const apiParams = useMemo(
    () => ({
      from: dateInputToIsoStart(filters.fromDate),
      to: dateInputToIsoNextDay(filters.toDate),
      mailbox: filters.mailbox.trim() || null,
      limit: emailPageLimit,
    }),
    [filters.fromDate, filters.mailbox, filters.toDate],
  )
  const emails = useEmailsInfinite(apiParams)
  const { fetchNextPage } = emails
  const emailDetail = useEmailDetail(recordId)
  const emailItems =
    emails.data?.pages
      .flatMap((page) => page.items)
      .filter((item) => matchesSearch(item, search))
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

  const closeEmailModal = useCallback(() => {
    navigate('/')
  }, [navigate])

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.hero}>
          <div className={styles.headerRow}>
            <h1 className={styles.brand}>Mail Agent</h1>
            <nav className={styles.nav} aria-label="Основная навигация">
              <Link
                className={`${styles.navLink} ${styles.activeNavLink}`}
                to="/"
              >
                Письма
              </Link>
              <Link className={styles.navLink} to="/statistics">
                Статистика
              </Link>
            </nav>
            <div className={styles.statusGroup}>
              <HealthIndicator />
            </div>
          </div>
        </header>

        <div className={styles.contentGrid}>
          <div className={styles.listColumn}>
            <DashboardFilters
              onChange={setFilters}
              placement="sidebar"
              value={filters}
            />
            <EmailList
              hasNextPage={emails.hasNextPage}
              isError={emails.isError}
              isFetchingNextPage={emails.isFetchingNextPage}
              isLoading={emails.isLoading}
              items={emailItems}
              nextCursor={nextEmailCursor}
              onLoadMore={loadMoreEmails}
              onSearchChange={setSearch}
              onSelect={selectEmail}
              search={search}
              selectedId={recordId}
            />
          </div>
        </div>

        {recordId && (
          <Modal
            onClose={closeEmailModal}
            title={emailDetail.data?.subject || 'Письмо'}
          >
            <EmailDetailPanel
              data={emailDetail.data}
              isError={emailDetail.isError}
              isLoading={emailDetail.isLoading}
              isPlaceholder={false}
            />
          </Modal>
        )}
      </div>
    </main>
  )
}
