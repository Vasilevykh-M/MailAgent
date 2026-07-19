import { Search } from 'lucide-react'

import { Button, Card } from '../../../shared'

import styles from './DashboardFilters.module.css'

export type DashboardFiltersValue = {
  fromDate: string
  toDate: string
  mailbox: string
  search: string
}

type DashboardFiltersProps = {
  value: DashboardFiltersValue
  isRefreshing: boolean
  onChange: (value: DashboardFiltersValue) => void
  onRefresh: () => void
}

export function DashboardFilters({
  value,
  isRefreshing,
  onChange,
  onRefresh,
}: DashboardFiltersProps) {
  return (
    <Card className={styles.card} variant="muted">
      <div className={styles.grid}>
        <label className={styles.field}>
          <span>С даты</span>
          <input
            onChange={(event) =>
              onChange({ ...value, fromDate: event.target.value })
            }
            type="date"
            value={value.fromDate}
          />
        </label>
        <label className={styles.field}>
          <span>По дату</span>
          <input
            onChange={(event) =>
              onChange({ ...value, toDate: event.target.value })
            }
            type="date"
            value={value.toDate}
          />
        </label>
        <label className={styles.field}>
          <span>Mailbox</span>
          <input
            onChange={(event) =>
              onChange({ ...value, mailbox: event.target.value })
            }
            placeholder="INBOX"
            value={value.mailbox}
          />
        </label>
        <label className={`${styles.field} ${styles.searchField}`}>
          <span>Локальный поиск</span>
          <div className={styles.searchBox}>
            <Search aria-hidden="true" size={16} />
            <input
              onChange={(event) =>
                onChange({ ...value, search: event.target.value })
              }
              placeholder="Тема, отправитель, summary"
              value={value.search}
            />
          </div>
        </label>
        <Button disabled={isRefreshing} onClick={onRefresh} variant="primary">
          {isRefreshing ? 'Обновление' : 'Обновить'}
        </Button>
      </div>
    </Card>
  )
}
