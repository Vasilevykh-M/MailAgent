import { useMemo, useState } from 'react'

import { useStatistics } from '../../../api'
import {
  dateInputToIsoNextDay,
  dateInputToIsoStart,
  isDateInputRangeValid,
  PageShell,
  TabsNav,
  useDebouncedValue,
} from '../../../shared'
import { UserMenu } from '../../auth'
import { DashboardFilters, defaultFilters } from '../DashboardFilters'
import { HealthIndicator } from '../HealthIndicator'
import { StatisticsCards } from '../StatisticsCards'
import { StatisticsCharts } from '../StatisticsCharts'

import styles from './StatisticsPage.module.css'

export function StatisticsPage() {
  const [filters, setFilters] = useState(defaultFilters)
  const debouncedMailbox = useDebouncedValue(filters.mailbox)
  const apiParams = useMemo(
    () => ({
      from: dateInputToIsoStart(filters.fromDate),
      to: dateInputToIsoNextDay(filters.toDate),
      mailbox: debouncedMailbox.trim() || null,
    }),
    [debouncedMailbox, filters.fromDate, filters.toDate],
  )
  const hasValidDateRange = isDateInputRangeValid(
    filters.fromDate,
    filters.toDate,
  )
  const statistics = useStatistics(apiParams, hasValidDateRange)

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
            { label: 'Письма', to: '/' },
            { active: true, label: 'Статистика', to: '/statistics' },
          ]}
        />
      }
      title="Mail Agent"
    >
      <div className={styles.contentGrid}>
        <DashboardFilters
          onChange={setFilters}
          placement="sidebar"
          showListFilters={false}
          value={filters}
        />

        <div className={styles.mainColumn}>
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
        </div>
      </div>
    </PageShell>
  )
}
