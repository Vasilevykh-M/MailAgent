import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useStatistics } from '../../../api'
import { dateInputToIsoNextDay, dateInputToIsoStart } from '../../../shared'
import { DashboardFilters, defaultFilters } from '../DashboardFilters'
import { HealthIndicator } from '../HealthIndicator'
import { StatisticsCards } from '../StatisticsCards'
import { StatisticsCharts } from '../StatisticsCharts'

import styles from './StatisticsPage.module.css'

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
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.hero}>
          <div className={styles.headerRow}>
            <h1 className={styles.brand}>Mail Agent</h1>
            <nav className={styles.nav} aria-label="Основная навигация">
              <Link className={styles.navLink} to="/">
                Письма
              </Link>
              <Link
                className={`${styles.navLink} ${styles.activeNavLink}`}
                to="/statistics"
              >
                Статистика
              </Link>
            </nav>
            <div className={styles.statusGroup}>
              <HealthIndicator />
            </div>
          </div>
        </header>

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
      </div>
    </main>
  )
}
