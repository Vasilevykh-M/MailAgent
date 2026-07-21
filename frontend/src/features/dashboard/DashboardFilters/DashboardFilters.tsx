import { ChevronDown, SlidersHorizontal } from 'lucide-react'

import { Field, Input, MultiSelect } from '../../../shared'

import styles from './DashboardFilters.module.css'

type AttachmentFilterValue = 'with' | 'without'
type ConfidenceFilterValue = 'high' | 'medium' | 'low' | 'none'
type StatusFilterValue =
  | 'classified'
  | 'new_project'
  | 'manual_review'
  | 'uncached'

export type DashboardFiltersValue = {
  fromDate: string
  toDate: string
  mailbox: string
  attachmentFilter: AttachmentFilterValue[]
  confidenceFilter: ConfidenceFilterValue[]
  statusFilter: StatusFilterValue[]
}

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
          <p className={styles.groupTitle}>Период</p>
          <div className={styles.groupGrid}>
            <Field label="С даты">
              <Input
                onChange={(event) =>
                  onChange({
                    ...value,
                    fromDate: event.target.value,
                  })
                }
                type="date"
                value={value.fromDate}
              />
            </Field>
            <Field label="По дату">
              <Input
                onChange={(event) =>
                  onChange({
                    ...value,
                    toDate: event.target.value,
                  })
                }
                type="date"
                value={value.toDate}
              />
            </Field>
            <Field label="Mailbox">
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
        {showListFilters && (
          <div className={styles.group}>
            <p className={styles.groupTitle}>Список</p>
            <div className={styles.groupGrid}>
              <Field label="Вложения">
                <MultiSelect
                  onChange={(attachmentFilter) =>
                    onChange({ ...value, attachmentFilter })
                  }
                  options={[
                    { label: 'С вложениями', value: 'with' },
                    { label: 'Без вложений', value: 'without' },
                  ]}
                  placeholder="Все"
                  value={value.attachmentFilter}
                />
              </Field>
              <Field label="Уверенность">
                <MultiSelect
                  onChange={(confidenceFilter) =>
                    onChange({ ...value, confidenceFilter })
                  }
                  options={[
                    { label: 'Высокая', value: 'high' },
                    { label: 'Средняя', value: 'medium' },
                    { label: 'Низкая', value: 'low' },
                    { label: 'Нет оценки', value: 'none' },
                  ]}
                  placeholder="Любая"
                  value={value.confidenceFilter}
                />
              </Field>
              <Field label="Статус">
                <MultiSelect
                  onChange={(statusFilter) =>
                    onChange({ ...value, statusFilter })
                  }
                  options={[
                    {
                      label: 'Классифицировано',
                      value: 'classified',
                    },
                    {
                      label: 'Новый проект',
                      value: 'new_project',
                    },
                    {
                      label: 'Ручная проверка',
                      value: 'manual_review',
                    },
                    {
                      label: 'Без данных статуса',
                      value: 'uncached',
                    },
                  ]}
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
