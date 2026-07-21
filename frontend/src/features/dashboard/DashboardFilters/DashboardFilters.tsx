import { ChevronDown, SlidersHorizontal } from 'lucide-react'

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

type FilterOption<Value extends string> = {
  label: string
  value: Value
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
            <label className={styles.field}>
              <span>С даты</span>
              <input
                onChange={(event) =>
                  onChange({
                    ...value,
                    fromDate: event.target.value,
                  })
                }
                type="date"
                value={value.fromDate}
              />
            </label>
            <label className={styles.field}>
              <span>По дату</span>
              <input
                onChange={(event) =>
                  onChange({
                    ...value,
                    toDate: event.target.value,
                  })
                }
                type="date"
                value={value.toDate}
              />
            </label>
            <label className={styles.field}>
              <span>Mailbox</span>
              <input
                onChange={(event) =>
                  onChange({
                    ...value,
                    mailbox: event.target.value,
                  })
                }
                placeholder="INBOX"
                value={value.mailbox}
              />
            </label>
          </div>
        </div>
        {showListFilters && (
          <div className={styles.group}>
            <p className={styles.groupTitle}>Список</p>
            <div className={styles.groupGrid}>
              <CheckboxDropdown
                label="Вложения"
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
              <CheckboxDropdown
                label="Уверенность"
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
              <CheckboxDropdown
                label="Статус"
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

type CheckboxDropdownProps<Value extends string> = {
  label: string
  options: FilterOption<Value>[]
  placeholder: string
  value: Value[]
  onChange: (value: Value[]) => void
}

function CheckboxDropdown<Value extends string>({
  label,
  options,
  placeholder,
  value,
  onChange,
}: CheckboxDropdownProps<Value>) {
  const selectedLabels = options
    .filter((option) => value.includes(option.value))
    .map((option) => option.label)
  const summary =
    selectedLabels.length > 0 ? selectedLabels.join(', ') : placeholder

  function toggle(optionValue: Value) {
    if (value.includes(optionValue)) {
      onChange(value.filter((selected) => selected !== optionValue))
      return
    }

    onChange([...value, optionValue])
  }

  return (
    <div className={styles.field}>
      <span>{label}</span>
      <details className={styles.dropdown}>
        <summary className={styles.dropdownSummary}>
          <span>{summary}</span>
          <ChevronDown aria-hidden="true" size={16} />
        </summary>
        <div className={styles.dropdownMenu}>
          {options.map((option) => (
            <label className={styles.checkboxOption} key={option.value}>
              <input
                checked={value.includes(option.value)}
                onChange={() => toggle(option.value)}
                type="checkbox"
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </details>
    </div>
  )
}
