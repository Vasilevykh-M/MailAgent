import type { StatisticsResponse } from '../../../api'
import { Card, EmptyState } from '../../../shared'
import { formatInteger } from '../../../shared'

import styles from './StatisticsCards.module.css'

type StatisticsCardsProps = {
  data: StatisticsResponse | undefined
  isLoading: boolean
  isError: boolean
}

function countByStatus(data: StatisticsResponse | undefined, status: string) {
  return (
    data?.classifications
      .filter((item) => item.status === status)
      .reduce((total, item) => total + item.count, 0) ?? 0
  )
}

function topClass(data: StatisticsResponse | undefined) {
  return data?.classifications.find((item) => item.class_name_ru)?.class_name_ru
}

export function StatisticsCards({
  data,
  isLoading,
  isError,
}: StatisticsCardsProps) {
  if (isLoading) {
    return (
      <section className={styles.grid} aria-label="Статистика">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card className={styles.metric} key={index} variant="muted">
            <div className={styles.skeletonTitle} />
            <div className={styles.skeletonValue} />
          </Card>
        ))}
      </section>
    )
  }

  if (isError) {
    return (
      <EmptyState
        description="Проверьте доступность Results API или параметры периода."
        title="Статистика недоступна"
      />
    )
  }

  const metrics = [
    {
      label: 'Писем',
      value: formatInteger(data?.total_emails ?? 0),
    },
    {
      label: 'Вложений',
      value: formatInteger(data?.total_attachments ?? 0),
    },
    {
      label: 'Ручная проверка',
      value: formatInteger(countByStatus(data, 'manual_review')),
    },
    {
      label: 'Топ класс',
      value: topClass(data) ?? 'нет данных',
    },
  ]

  return (
    <section className={styles.grid} aria-label="Статистика">
      {metrics.map((metric) => (
        <Card className={styles.metric} key={metric.label} variant="muted">
          <p className={styles.label}>{metric.label}</p>
          <p className={styles.value}>{metric.value}</p>
        </Card>
      ))}
    </section>
  )
}
