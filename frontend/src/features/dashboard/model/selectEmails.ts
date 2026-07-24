import type { EmailDetail, EmailListItem } from '../../../api'
import type { DashboardFiltersValue } from './filters'

type CachedEmailDetail = Pick<EmailDetail, 'classification'>
type EmailListFilters = Pick<
  DashboardFiltersValue,
  'attachmentFilter' | 'classFilter' | 'statusFilter'
>

type SelectVisibleEmailsOptions = {
  detailsById: ReadonlyMap<string, CachedEmailDetail>
  filters: EmailListFilters
  items: EmailListItem[]
  search: string
}

export function selectVisibleEmails({
  detailsById,
  filters,
  items,
  search,
}: SelectVisibleEmailsOptions): EmailListItem[] {
  const normalizedSearch = search.trim().toLowerCase()
  const visibleItems: EmailListItem[] = []

  for (const item of items) {
    const detail = detailsById.get(item.id)
    const enrichedItem = {
      ...item,
      class_code: item.class_code ?? detail?.classification?.class_code,
      class_name_ru:
        item.class_name_ru ?? detail?.classification?.class_name_ru,
    }

    if (
      matchesSearch(enrichedItem, normalizedSearch) &&
      matchesAttachmentFilter(enrichedItem, filters.attachmentFilter) &&
      matchesClassFilter(enrichedItem, filters.classFilter) &&
      matchesStatusFilter(detail, filters.statusFilter)
    ) {
      visibleItems.push(enrichedItem)
    }
  }

  return visibleItems
}

function matchesSearch(item: EmailListItem, normalizedSearch: string): boolean {
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
): boolean {
  if (filter.length === 0) {
    return true
  }

  return filter.some((filterValue) =>
    filterValue === 'with'
      ? item.attachment_count > 0
      : item.attachment_count === 0,
  )
}

function matchesClassFilter(
  item: EmailListItem,
  filter: DashboardFiltersValue['classFilter'],
): boolean {
  if (filter.length === 0) {
    return true
  }

  return filter.some((filterValue) =>
    filterValue === 'none' ? !item.class_code : item.class_code === filterValue,
  )
}

function matchesStatusFilter(
  detail: CachedEmailDetail | undefined,
  filter: DashboardFiltersValue['statusFilter'],
): boolean {
  if (filter.length === 0) {
    return true
  }

  return filter.some((filterValue) =>
    filterValue === 'uncached'
      ? !detail
      : detail?.classification?.status === filterValue,
  )
}
