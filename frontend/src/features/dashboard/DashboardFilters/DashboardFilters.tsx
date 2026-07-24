import { ChevronDown, SlidersHorizontal } from 'lucide-react'

import { DateRangePicker, Field, Input, MultiSelect } from '../../../shared'
import {
  attachmentFilterOptions,
  classFilterOptions,
  statusFilterOptions,
  type DashboardFiltersValue,
} from '../model'

import styles from './DashboardFilters.module.css'

type DashboardFiltersProps = {
  value: DashboardFiltersValue
  onChange: (value: DashboardFiltersValue) => void
  placement?: 'bar' | 'sidebar'
  showListFilters?: boolean
}

export function DashboardFilters({
  value,
  onChange,
  placement = 'bar',
  showListFilters = true,
}: DashboardFiltersProps) {
  const content = (
    <>
      <div className={styles.panelHeader}>
        <span className={styles.summaryTitle}>
          <SlidersHorizontal aria-hidden="true" size={16} />
          Фильтры
        </span>
      </div>
      <div className={styles.body}>
        <div className={styles.group}>
          <p className={styles.groupTitle}>Mailbox</p>
          <div className={styles.groupGrid}>
            <Field label="Почтовый ящик">
              <Input
                onChange={(event) =>
                  onChange({
                    ...value,
                    mailbox: event.target.value,
                  })
                }
                placeholder="INBOX"
                value={value.mailbox}
              />
            </Field>
          </div>
        </div>
        <div className={styles.group}>
          <p className={styles.groupTitle}>Период</p>
          <div className={styles.groupGrid}>
            <Field label="Диапазон">
              <DateRangePicker
                onChange={(range) =>
                  onChange({
                    ...value,
                    fromDate: range.from,
                    toDate: range.to,
                  })
                }
                value={{
                  from: value.fromDate,
                  to: value.toDate,
                }}
              />
            </Field>
          </div>
        </div>
        {showListFilters && (
          <div className={styles.group}>
            <p className={styles.groupTitle}>Список</p>
            <div className={styles.groupGrid}>
              <Field label="Класс">
                <MultiSelect
                  ariaLabel="Выбор класса"
                  onChange={(classFilter) =>
                    onChange({ ...value, classFilter })
                  }
                  options={classFilterOptions}
                  placeholder="Все"
                  value={value.classFilter}
                />
              </Field>
              <Field label="Вложения">
                <MultiSelect
                  ariaLabel="Выбор наличия вложений"
                  onChange={(attachmentFilter) =>
                    onChange({ ...value, attachmentFilter })
                  }
                  options={attachmentFilterOptions}
                  placeholder="Все"
                  value={value.attachmentFilter}
                />
              </Field>
              <Field label="Статус">
                <MultiSelect
                  ariaLabel="Выбор статуса"
                  onChange={(statusFilter) =>
                    onChange({ ...value, statusFilter })
                  }
                  options={statusFilterOptions}
                  placeholder="Все"
                  value={value.statusFilter}
                />
              </Field>
            </div>
          </div>
        )}
      </div>
    </>
  )

  if (placement === 'sidebar') {
    return (
      <aside className={`${styles.panel} ${styles.sidebar}`}>{content}</aside>
    )
  }

  return (
    <details className={`${styles.panel} ${styles[placement]}`}>
      <summary className={styles.summary}>
        <span className={styles.summaryTitle}>
          <SlidersHorizontal aria-hidden="true" size={16} />
          Фильтры
        </span>
        <ChevronDown
          aria-hidden="true"
          className={styles.summaryIcon}
          size={16}
        />
      </summary>
      {content}
    </details>
  )
}
