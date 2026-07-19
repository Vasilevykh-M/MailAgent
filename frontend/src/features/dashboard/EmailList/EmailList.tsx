import type { EmailListItem } from '../../../api'
import { Badge, Button, Card, EmptyState } from '../../../shared'
import {
  formatConfidence,
  formatDateTime,
  getConfidenceTone,
} from '../../../shared'

import styles from './EmailList.module.css'

type EmailListProps = {
  items: EmailListItem[]
  hasNextPage: boolean
  isLoading: boolean
  isError: boolean
  isFetchingNextPage: boolean
  selectedId: string | null
  onLoadMore: () => void
  onSelect: (recordId: string) => void
}

export function EmailList({
  items,
  hasNextPage,
  isLoading,
  isError,
  isFetchingNextPage,
  selectedId,
  onLoadMore,
  onSelect,
}: EmailListProps) {
  if (isLoading) {
    return (
      <Card title="Письма" variant="muted">
        <div className={styles.loadingList}>
          {Array.from({ length: 5 }).map((_, index) => (
            <div className={styles.skeletonRow} key={index} />
          ))}
        </div>
      </Card>
    )
  }

  if (isError) {
    return (
      <Card title="Письма" variant="muted">
        <EmptyState
          description="Не удалось получить список писем из Results API."
          title="Список недоступен"
        />
      </Card>
    )
  }

  if (items.length === 0) {
    return (
      <Card title="Письма" variant="muted">
        <EmptyState
          description="Измените период или mailbox, если ожидаете данные."
          title="За выбранный период писем нет"
        />
      </Card>
    )
  }

  return (
    <Card
      actions={
        hasNextPage ? (
          <Button disabled={isFetchingNextPage} onClick={onLoadMore}>
            {isFetchingNextPage ? 'Загрузка' : 'Загрузить ещё'}
          </Button>
        ) : null
      }
      description="Локальный поиск применяется только к загруженным страницам."
      title="Письма"
      variant="muted"
    >
      <div className={styles.list}>
        {items.map((item) => (
          <button
            aria-pressed={item.id === selectedId}
            className={`${styles.row} ${item.id === selectedId ? styles.selected : ''}`}
            key={item.id}
            onClick={() => onSelect(item.id)}
            type="button"
          >
            <div className={styles.rowHeader}>
              <h3>{item.subject || 'Без темы'}</h3>
              <Badge tone={getConfidenceTone(item.confidence)}>
                {formatConfidence(item.confidence)}
              </Badge>
            </div>
            <p className={styles.preview}>{item.summary_preview}</p>
            <div className={styles.meta}>
              <span>{item.from}</span>
              <span>{formatDateTime(item.received_at)}</span>
              <span>{item.attachment_count} влож.</span>
            </div>
          </button>
        ))}
      </div>
    </Card>
  )
}
