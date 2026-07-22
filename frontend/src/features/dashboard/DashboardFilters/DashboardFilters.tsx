import { ChevronDown, SlidersHorizontal } from 'lucide-react'

import { DateRangePicker, Field, Input, MultiSelect } from '../../../shared'

import styles from './DashboardFilters.module.css'

type AttachmentFilterValue = 'with' | 'without'
type ClassFilterValue =
  | '3D_PRINTERS'
  | 'CHEMISTRY'
  | 'FOUNDRY'
  | 'MOLD_PRINTING'
  | 'ROBOTIC_CELLS'
  | 'PRODUCTION_LINES'
  | 'MACHINES'
  | 'TECHNICAL_VISION'
  | 'OTHER_EQUIPMENT'
  | 'none'
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
  classFilter: ClassFilterValue[]
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
                  onChange={(classFilter) =>
                    onChange({ ...value, classFilter })
                  }
                  options={[
                    { label: '3D-принтеры', value: '3D_PRINTERS' },
                    { label: 'Химия', value: 'CHEMISTRY' },
                    { label: 'Литьё', value: 'FOUNDRY' },
                    { label: 'Печать форм', value: 'MOLD_PRINTING' },
                    {
                      label: 'Роботизированные ячейки',
                      value: 'ROBOTIC_CELLS',
                    },
                    {
                      label: 'Производственные линии',
                      value: 'PRODUCTION_LINES',
                    },
                    { label: 'Станки', value: 'MACHINES' },
                    {
                      label: 'Техническое зрение',
                      value: 'TECHNICAL_VISION',
                    },
                    { label: 'Другое оборудование', value: 'OTHER_EQUIPMENT' },
                    { label: 'Без класса', value: 'none' },
                  ]}
                  placeholder="Все"
                  value={value.classFilter}
                />
              </Field>
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
