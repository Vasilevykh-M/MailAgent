import { useEffect, useRef } from 'react'

import type { EmailListItem } from '../../../api'
import { Badge, Card, EmptyState } from '../../../shared'
import {
  formatConfidence,
  formatDateTime,
  getConfidenceTone,
  useIntersectionObserver,
} from '../../../shared'

import styles from './EmailList.module.css'

const autoLoadThrottleMs = 1000

type EmailListProps = {
  items: EmailListItem[]
  hasNextPage: boolean
  isLoading: boolean
  isError: boolean
  isFetchingNextPage: boolean
  nextCursor: string | null
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
  nextCursor,
  selectedId,
  onLoadMore,
  onSelect,
}: EmailListProps) {
  const { isIntersecting, targetRef } =
    useIntersectionObserver<HTMLDivElement>()
  const lastAutoLoadedCursorRef = useRef<string | null>(null)
  const lastAutoLoadAtRef = useRef(0)
  const pendingAutoLoadRef = useRef<number | null>(null)

  useEffect(() => {
    if (pendingAutoLoadRef.current !== null) {
      window.clearTimeout(pendingAutoLoadRef.current)
      pendingAutoLoadRef.current = null
    }

    if (
      !isIntersecting ||
      !hasNextPage ||
      isFetchingNextPage ||
      !nextCursor ||
      lastAutoLoadedCursorRef.current === nextCursor
    ) {
      return
    }

    const now = Date.now()
    const elapsed = now - lastAutoLoadAtRef.current

    if (elapsed >= autoLoadThrottleMs) {
      lastAutoLoadedCursorRef.current = nextCursor
      lastAutoLoadAtRef.current = now
      onLoadMore()
      return
    }

    pendingAutoLoadRef.current = window.setTimeout(() => {
      lastAutoLoadedCursorRef.current = nextCursor
      lastAutoLoadAtRef.current = Date.now()
      onLoadMore()
    }, autoLoadThrottleMs - elapsed)

    return () => {
      if (pendingAutoLoadRef.current !== null) {
        window.clearTimeout(pendingAutoLoadRef.current)
        pendingAutoLoadRef.current = null
      }
    }
  }, [hasNextPage, isFetchingNextPage, isIntersecting, nextCursor, onLoadMore])

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
        <div aria-hidden="true" className={styles.sentinel} ref={targetRef} />
      </div>
      {hasNextPage && (
        <p className={styles.autoLoadStatus}>
          {isFetchingNextPage
            ? 'Загружаем следующую страницу…'
            : 'Следующая страница загрузится автоматически внизу списка.'}
        </p>
      )}
    </Card>
  )
}
