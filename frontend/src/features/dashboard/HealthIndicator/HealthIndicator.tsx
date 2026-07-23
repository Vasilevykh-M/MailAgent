import { CircleCheck, CircleX, LoaderCircle } from 'lucide-react'

import { useHealthReady } from '../../../api'

import styles from './HealthIndicator.module.css'

export function HealthIndicator() {
  const health = useHealthReady()
  const isReady = health.data?.status === 'ok'

  if (health.isLoading) {
    return (
      <span
        aria-label="Проверка соединения"
        className={styles.icon}
        title="Проверка соединения"
      >
        <LoaderCircle
          aria-hidden="true"
          className={`${styles.neutral} ${styles.spin}`}
          size={18}
        />
      </span>
    )
  }

  if (health.isError) {
    return (
      <span
        aria-label="Нет соединения"
        className={styles.icon}
        title="Нет соединения"
      >
        <CircleX aria-hidden="true" className={styles.danger} size={18} />
      </span>
    )
  }

  const Icon = isReady ? CircleCheck : CircleX

  return (
    <span
      aria-label={isReady ? 'Есть соединение' : 'Сервис недоступен'}
      className={styles.icon}
      title={isReady ? 'Есть соединение' : 'Сервис недоступен'}
    >
      <Icon
        aria-hidden="true"
        className={isReady ? styles.success : styles.warning}
        size={18}
      />
    </span>
  )
}
