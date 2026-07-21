import { useMemo, useState } from 'react'

import { useStatistics } from '../../../api'
import {
  dateInputToIsoNextDay,
  dateInputToIsoStart,
  PageShell,
  TabsNav,
} from '../../../shared'
import { DashboardFilters, defaultFilters } from '../DashboardFilters'
import { HealthIndicator } from '../HealthIndicator'
import { StatisticsCards } from '../StatisticsCards'
import { StatisticsCharts } from '../StatisticsCharts'

export function StatisticsPage() {
  const [filters, setFilters] = useState(defaultFilters)
  const apiParams = useMemo(
    () => ({
      from: dateInputToIsoStart(filters.fromDate),
      to: dateInputToIsoNextDay(filters.toDate),
      mailbox: filters.mailbox.trim() || null,
    }),
    [filters.fromDate, filters.mailbox, filters.toDate],
  )
  const statistics = useStatistics(apiParams)

  return (
    <PageShell
      actions={<HealthIndicator />}
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
      <DashboardFilters
        onChange={setFilters}
        showListFilters={false}
        value={filters}
      />

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
    </PageShell>
  )
}
