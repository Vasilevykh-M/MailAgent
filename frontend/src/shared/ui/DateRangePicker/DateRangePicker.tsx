import { CalendarDays, ChevronDown } from 'lucide-react'

import { formatDateInputDisplay } from '../../lib'
import { Button } from '../Button'
import { Dropdown } from '../Dropdown'
import { Field } from '../Field'
import { Input } from '../Input'

import styles from './DateRangePicker.module.css'

export type DateRangeValue = {
  from: string
  to: string
}

type DateRangePickerProps = {
  value: DateRangeValue
  onChange: (value: DateRangeValue) => void
}

export function DateRangePicker({ value, onChange }: DateRangePickerProps) {
  const hasRange = value.from || value.to
  const isInvalid = Boolean(value.from && value.to && value.from > value.to)
  const summary = hasRange
    ? `${value.from ? formatDateInputDisplay(value.from) : '—'} — ${
        value.to ? formatDateInputDisplay(value.to) : '—'
      }`
    : 'Выберите период'

  return (
    <Dropdown>
      <Dropdown.Trigger>
        <Button className={styles.trigger} variant="secondary">
          <CalendarDays aria-hidden="true" size={16} />
          <span className={styles.triggerText}>{summary}</span>
          <ChevronDown
            aria-hidden="true"
            className={styles.triggerIcon}
            size={16}
          />
        </Button>
      </Dropdown.Trigger>
      <Dropdown.Content className={styles.content}>
        <div className={styles.grid}>
          <Field label="С даты">
            <Input
              invalid={isInvalid}
              onChange={(event) =>
                onChange({ ...value, from: event.target.value })
              }
              type="date"
              value={value.from}
            />
          </Field>
          <Field label="По дату">
            <Input
              invalid={isInvalid}
              onChange={(event) =>
                onChange({ ...value, to: event.target.value })
              }
              type="date"
              value={value.to}
            />
          </Field>
        </div>
        {isInvalid && (
          <p className={styles.error}>
            Начало периода должно быть раньше конца.
          </p>
        )}
        {hasRange && (
          <div className={styles.actions}>
            <Button
              onClick={() => onChange({ from: '', to: '' })}
              variant="ghost"
            >
              Очистить
            </Button>
          </div>
        )}
      </Dropdown.Content>
    </Dropdown>
  )
}
