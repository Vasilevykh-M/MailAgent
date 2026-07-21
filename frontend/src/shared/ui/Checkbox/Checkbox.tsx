import type { InputHTMLAttributes, ReactNode } from 'react'

import styles from './Checkbox.module.css'

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  children: ReactNode
}

export function Checkbox({ children, className, ...props }: CheckboxProps) {
  const classNames = [styles.checkbox, className].filter(Boolean).join(' ')

  return (
    <label className={classNames}>
      <input type="checkbox" {...props} />
      <span>{children}</span>
    </label>
  )
}
