import type { ReactNode } from 'react'

import styles from './Field.module.css'

type FieldProps = {
  children: ReactNode
  error?: ReactNode
  hint?: ReactNode
  label: ReactNode
}

export function Field({ children, error, hint, label }: FieldProps) {
  return (
    <label className={styles.field}>
      <span className={styles.label}>{label}</span>
      {children}
      {hint && <span className={styles.hint}>{hint}</span>}
      {error && <span className={styles.error}>{error}</span>}
    </label>
  )
}
