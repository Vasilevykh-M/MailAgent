import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  queryKeys,
  useEmailDetail,
  useEmailsInfinite,
  type EmailDetail,
  type EmailListItem,
} from '../../../api'
import {
  dateInputToIsoNextDay,
  dateInputToIsoStart,
  Modal,
  PageShell,
  TabsNav,
} from '../../../shared'
import { UserMenu } from '../../auth'
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

function matchesClassFilter(
  item: EmailListItem,
  detail: EmailDetail | undefined,
  filter: DashboardFiltersValue['classFilter'],
) {
  if (filter.length === 0) {
    return true
  }

  const classCode =
    item.class_code ?? detail?.classification?.class_code ?? null

  return filter.some((filterValue) => {
    if (filterValue === 'none') {
      return !classCode
    }

    return classCode === filterValue
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
      .map((item) => {
        const detail = queryClient.getQueryData<EmailDetail>(
          queryKeys.emails.detail(item.id),
        )

        return {
          ...item,
          class_code: item.class_code ?? detail?.classification?.class_code,
          class_name_ru:
            item.class_name_ru ?? detail?.classification?.class_name_ru,
        }
      })
      .filter((item) => matchesSearch(item, search))
      .filter((item) => matchesAttachmentFilter(item, filters.attachmentFilter))
      .filter((item) =>
        matchesClassFilter(
          item,
          queryClient.getQueryData<EmailDetail>(
            queryKeys.emails.detail(item.id),
          ),
          filters.classFilter,
        ),
      )
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
