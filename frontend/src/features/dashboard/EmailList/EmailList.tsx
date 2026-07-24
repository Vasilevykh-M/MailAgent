import { Search } from 'lucide-react'
import { useEffect, useRef } from 'react'

import type { EmailListItem } from '../../../api'
import {
  Badge,
  Card,
  DataList,
  EmptyState,
  Field,
  Input,
  Skeleton,
} from '../../../shared'
import { formatDateTime, useIntersectionObserver } from '../../../shared'
import { ApiErrorState } from '../ApiErrorState'
import {
  getClassificationClassLabel,
  isClassificationClassCode,
  type ClassificationClassCode,
} from '../model'

import styles from './EmailList.module.css'

const autoLoadThrottleMs = 1000
const classBadgeClasses: Record<ClassificationClassCode, string> = {
  '3D_PRINTERS': styles.class3dPrinters,
  CHEMISTRY: styles.classChemistry,
  FOUNDRY: styles.classFoundry,
  MOLD_PRINTING: styles.classMoldPrinting,
  ROBOTIC_CELLS: styles.classRoboticCells,
  PRODUCTION_LINES: styles.classProductionLines,
  MACHINES: styles.classMachines,
  TECHNICAL_VISION: styles.classTechnicalVision,
  OTHER_EQUIPMENT: styles.classOtherEquipment,
}

type EmailListProps = {
  items: EmailListItem[]
  hasNextPage: boolean
  isLoading: boolean
  error: unknown
  isFetchingNextPage: boolean
  nextCursor: string | null
  selectedId: string | null
  search: string
  onLoadMore: () => void
  onRetry: () => void
  onSearchChange: (search: string) => void
  onSelect: (recordId: string) => void
}

function getClassBadgeClass(classCode: string | null | undefined) {
  return classCode && isClassificationClassCode(classCode)
    ? classBadgeClasses[classCode]
    : styles.classNone
}

export function EmailList({
  items,
  hasNextPage,
  isLoading,
  error,
  isFetchingNextPage,
  nextCursor,
  selectedId,
  search,
  onLoadMore,
  onRetry,
  onSearchChange,
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
      <Card className={styles.card} title="Письма" variant="muted">
        <div className={styles.loadingList}>
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton height={76} key={index} />
          ))}
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className={styles.card} title="Письма" variant="muted">
        <ApiErrorState
          description="Не удалось получить список писем из Results API."
          error={error}
          onRetry={onRetry}
          title="Список недоступен"
        />
      </Card>
    )
  }

  return (
    <Card className={styles.card} title="Письма" variant="muted">
      <div className={styles.searchField}>
        <Field label="Поиск по загруженным письмам">
          <Input
            leftSlot={<Search aria-hidden="true" size={16} />}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Тема, отправитель, summary"
            value={search}
          />
        </Field>
      </div>
      {items.length === 0 ? (
        <div className={styles.scrollArea}>
          <EmptyState
            description={
              search.trim()
                ? 'Измените поисковый запрос или сбросьте дополнительные фильтры.'
                : 'Измените период или mailbox, если ожидаете данные.'
            }
            title={search.trim() ? 'Поиск ничего не нашёл' : 'Писем нет'}
          />
        </div>
      ) : (
        <div className={styles.scrollArea}>
          <DataList>
            {items.map((item) => (
              <DataList.Item
                badge={
                  <Badge
                    className={`${styles.classBadge} ${getClassBadgeClass(item.class_code)}`}
                    tone="neutral"
                  >
                    {getClassificationClassLabel(
                      item.class_code,
                      item.class_name_ru,
                    )}
                  </Badge>
                }
                description={item.summary_preview}
                key={item.id}
                meta={[
                  item.from,
                  formatDateTime(item.received_at),
                  `${item.attachment_count} влож.`,
                ]}
                onClick={() => onSelect(item.id)}
                selected={item.id === selectedId}
                title={item.subject || 'Без темы'}
              />
            ))}
            <div
              aria-hidden="true"
              className={styles.sentinel}
              ref={targetRef}
            />
          </DataList>
          {hasNextPage && (
            <p className={styles.autoLoadStatus}>
              {isFetchingNextPage ? 'Загружаем письма…' : 'Прокрутите ниже'}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}
