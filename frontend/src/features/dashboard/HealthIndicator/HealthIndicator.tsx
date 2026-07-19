import { Activity } from 'lucide-react'

import { useHealthReady } from '../../../api'
import { Badge } from '../../../shared'

import styles from './HealthIndicator.module.css'

export function HealthIndicator() {
  const health = useHealthReady()
  const isReady = health.data?.status === 'ok'

  if (health.isLoading) {
    return <Badge tone="neutral">Проверка API</Badge>
  }

  if (health.isError) {
    return <Badge tone="danger">API недоступен</Badge>
  }

  return (
    <Badge tone={isReady ? 'success' : 'warning'}>
      <span className={styles.content}>
        <Activity aria-hidden="true" size={14} />
        {isReady ? 'API готов' : 'API unavailable'}
      </span>
    </Badge>
  )
}
