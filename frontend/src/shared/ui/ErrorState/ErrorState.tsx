import type { ReactNode } from 'react'

import { Button } from '../Button'
import { EmptyState } from '../EmptyState'

import styles from './ErrorState.module.css'

type ErrorStateProps = {
  title: ReactNode
  description?: ReactNode
  details?: ReactNode
  onRetry?: () => void
  retryLabel?: string
}

export function ErrorState({
  title,
  description,
  details,
  onRetry,
  retryLabel = 'Повторить',
}: ErrorStateProps) {
  return (
    <div className={styles.root} role="alert">
      <EmptyState
        action={
          onRetry ? (
            <Button onClick={onRetry} variant="secondary">
              {retryLabel}
            </Button>
          ) : undefined
        }
        description={
          <>
            {description}
            {details && <code className={styles.details}>{details}</code>}
          </>
        }
        title={title}
      />
    </div>
  )
}
