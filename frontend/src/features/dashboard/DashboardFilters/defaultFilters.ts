import { apiConfig } from '../../../api/config'
import { formatDateForInput } from '../../../shared'
import type { DashboardFiltersValue } from './DashboardFilters'

export function defaultFilters(): DashboardFiltersValue {
  const today = new Date()
  const monthStart = new Date(today)

  monthStart.setDate(1)

  return {
    fromDate: formatDateForInput(monthStart),
    toDate: formatDateForInput(today),
    mailbox: apiConfig.defaultMailbox,
    attachmentFilter: [],
    confidenceFilter: [],
    statusFilter: [],
  }
}
