import { Search } from 'lucide-react'

import { Card } from '../../../shared'

import styles from './DashboardFilters.module.css'

export type DashboardFiltersValue = {
  fromDate: string
  toDate: string
  mailbox: string
  search: string
  attachmentFilter: 'all' | 'with' | 'without'
  confidenceFilter: 'all' | 'high' | 'medium' | 'low' | 'none'
  statusFilter:
    | 'all'
    | 'classified'
    | 'new_project'
    | 'manual_review'
    | 'uncached'
}

type DashboardFiltersProps = {
  value: DashboardFiltersValue
  onChange: (value: DashboardFiltersValue) => void
}

export function DashboardFilters({ value, onChange }: DashboardFiltersProps) {
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
        <label className={styles.field}>
          <span>Вложения</span>
          <select
            onChange={(event) =>
              onChange({
                ...value,
                attachmentFilter: event.target
                  .value as DashboardFiltersValue['attachmentFilter'],
              })
            }
            value={value.attachmentFilter}
          >
            <option value="all">Все</option>
            <option value="with">С вложениями</option>
            <option value="without">Без вложений</option>
          </select>
        </label>
        <label className={styles.field}>
          <span>Уверенность</span>
          <select
            onChange={(event) =>
              onChange({
                ...value,
                confidenceFilter: event.target
                  .value as DashboardFiltersValue['confidenceFilter'],
              })
            }
            value={value.confidenceFilter}
          >
            <option value="all">Любая</option>
            <option value="high">Высокая</option>
            <option value="medium">Средняя</option>
            <option value="low">Низкая</option>
            <option value="none">Нет оценки</option>
          </select>
        </label>
        <label className={styles.field}>
          <span>Статус (кеш)</span>
          <select
            onChange={(event) =>
              onChange({
                ...value,
                statusFilter: event.target
                  .value as DashboardFiltersValue['statusFilter'],
              })
            }
            value={value.statusFilter}
          >
            <option value="all">Все</option>
            <option value="classified">Классифицировано</option>
            <option value="new_project">Новый проект</option>
            <option value="manual_review">Ручная проверка</option>
            <option value="uncached">Detail не загружен</option>
          </select>
        </label>
      </div>
    </Card>
  )
}
