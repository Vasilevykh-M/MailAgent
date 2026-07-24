import { ChevronDown } from 'lucide-react'

import { Button } from '../Button'
import { Checkbox } from '../Checkbox'
import { Dropdown } from '../Dropdown'

import styles from './MultiSelect.module.css'

export type MultiSelectOption<Value extends string> = {
  label: string
  value: Value
}

export type MultiSelectProps<Value extends string> = {
  options: ReadonlyArray<MultiSelectOption<Value>>
  placeholder: string
  value: Value[]
  onChange: (value: Value[]) => void
}

export function MultiSelect<Value extends string>({
  options,
  placeholder,
  value,
  onChange,
}: MultiSelectProps<Value>) {
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
    <Dropdown>
      <Dropdown.Trigger>
        <Button className={styles.trigger} variant="secondary">
          <span className={styles.triggerLabel}>{summary}</span>
          <ChevronDown
            aria-hidden="true"
            className={styles.triggerIcon}
            size={16}
          />
        </Button>
      </Dropdown.Trigger>
      <Dropdown.Content className={styles.menu}>
        {options.map((option) => (
          <Checkbox
            checked={value.includes(option.value)}
            key={option.value}
            onChange={() => toggle(option.value)}
          >
            {option.label}
          </Checkbox>
        ))}
      </Dropdown.Content>
    </Dropdown>
  )
}
