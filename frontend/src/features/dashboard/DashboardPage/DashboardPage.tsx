import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useDeferredValue, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  queryKeys,
  useEmailDetail,
  useEmailsInfinite,
  type EmailDetail,
} from '../../../api'
import {
  dateInputToIsoNextDay,
  dateInputToIsoStart,
  isDateInputRangeValid,
  Modal,
  PageShell,
  TabsNav,
  useDebouncedValue,
} from '../../../shared'
import { UserMenu } from '../../auth'
import { DashboardFilters, defaultFilters } from '../DashboardFilters'
import { EmailDetailPanel } from '../EmailDetailPanel'
import { EmailList } from '../EmailList'
import { HealthIndicator } from '../HealthIndicator'
import { selectVisibleEmails } from '../model'

import styles from './DashboardPage.module.css'

const emailPageLimit = 10

export function DashboardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { recordId = null } = useParams()
  const [filters, setFilters] = useState(defaultFilters)
  const [search, setSearch] = useState('')
  const debouncedMailbox = useDebouncedValue(filters.mailbox)
  const deferredSearch = useDeferredValue(search)
  const listFilters = useMemo(
    () => ({
      attachmentFilter: filters.attachmentFilter,
      classFilter: filters.classFilter,
      statusFilter: filters.statusFilter,
    }),
    [filters.attachmentFilter, filters.classFilter, filters.statusFilter],
  )
  const apiParams = useMemo(
    () => ({
      from: dateInputToIsoStart(filters.fromDate),
      to: dateInputToIsoNextDay(filters.toDate),
      mailbox: debouncedMailbox.trim() || null,
      limit: emailPageLimit,
    }),
    [debouncedMailbox, filters.fromDate, filters.toDate],
  )
  const hasValidDateRange = isDateInputRangeValid(
    filters.fromDate,
    filters.toDate,
  )
  const emails = useEmailsInfinite(apiParams, hasValidDateRange)
  const { fetchNextPage } = emails
  const emailDetail = useEmailDetail(recordId)
  const emailItems = useMemo(() => {
    const items = emails.data?.pages.flatMap((page) => page.items) ?? []
    const detailsById = new Map<string, EmailDetail>()

    for (const item of items) {
      const detail = queryClient.getQueryData<EmailDetail>(
        queryKeys.emails.detail(item.id),
      )

      if (detail) {
        detailsById.set(item.id, detail)
      }
    }

    if (recordId && emailDetail.data) {
      detailsById.set(recordId, emailDetail.data)
    }

    return selectVisibleEmails({
      detailsById,
      filters: listFilters,
      items,
      search: deferredSearch,
    })
  }, [
    deferredSearch,
    emailDetail.data,
    emails.data,
    listFilters,
    queryClient,
    recordId,
  ])
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
    <PageShell
      actions={
        <>
          <HealthIndicator />
          <UserMenu />
        </>
      }
      navigation={
        <TabsNav
          ariaLabel="Основная навигация"
          items={[
            { active: true, label: 'Письма', to: '/' },
            { label: 'Статистика', to: '/statistics' },
          ]}
        />
      }
      title="Mail Agent"
    >
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
    </PageShell>
  )
}
