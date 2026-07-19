import type { ReactNode } from 'react'

import styles from './EmptyState.module.css'

type EmptyStateProps = {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className={styles.emptyState}>
      <div className={styles.icon} aria-hidden="true" />
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  )
}
