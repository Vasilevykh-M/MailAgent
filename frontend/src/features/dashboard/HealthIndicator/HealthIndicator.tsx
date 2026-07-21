import { useHealthReady } from '../../../api'
import { Badge } from '../../../shared'

export function HealthIndicator() {
  const health = useHealthReady()
  const isReady = health.data?.status === 'ok'

  if (health.isLoading) {
    return <Badge tone="neutral">Проверка</Badge>
  }

  if (health.isError) {
    return <Badge tone="danger">Нет соединения</Badge>
  }

  return (
    <Badge tone={isReady ? 'success' : 'warning'}>
      {isReady ? 'Есть соединение' : 'Нет соединения'}
    </Badge>
  )
}
