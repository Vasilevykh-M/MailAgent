import type { InputHTMLAttributes, ReactNode } from 'react'

import styles from './Input.module.css'

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  invalid?: boolean
  leftSlot?: ReactNode
  rightSlot?: ReactNode
}

export function Input({
  className,
  invalid = false,
  leftSlot,
  rightSlot,
  ...props
}: InputProps) {
  const classNames = [
    styles.inputRoot,
    invalid ? styles.invalid : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <span className={classNames}>
      {leftSlot && <span className={styles.slot}>{leftSlot}</span>}
      <input className={styles.input} aria-invalid={invalid} {...props} />
      {rightSlot && <span className={styles.slot}>{rightSlot}</span>}
    </span>
  )
}
