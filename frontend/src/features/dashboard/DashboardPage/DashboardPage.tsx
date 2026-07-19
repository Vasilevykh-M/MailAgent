import { apiConfig } from '../../../api/config'
import { Alert, Badge, Button, Card, EmptyState } from '../../../shared'

import styles from './DashboardPage.module.css'

const plannedSections = [
  'Health indicator через /health/ready',
  'KPI и графики через /api/v1/statistics',
  'Список писем через /api/v1/emails',
  'Карточка письма через /api/v1/emails/{record_id}',
  'Скачивание вложений и исходного .eml',
]

export function DashboardPage() {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.hero}>
          <div className={styles.headerRow}>
            <p className={styles.eyebrow}>Mail Agent</p>
            <Badge tone="success">Dev mocks ready</Badge>
          </div>
          <div className={styles.heroContent}>
            <div>
              <h1 className={styles.title}>Dashboard обработанных писем</h1>
              <p className={styles.description}>
                Базовое React + TypeScript окружение готово. Следующие этапы —
                API client, TanStack Query hooks и рабочие виджеты dashboard.
              </p>
            </div>
            <div className={styles.configCard}>
              <div>
                API: <span>{apiConfig.baseUrl}</span>
              </div>
              <div>
                Mailbox: <span>{apiConfig.defaultMailbox}</span>
              </div>
            </div>
          </div>
        </header>

        <Alert title="Двигаемся постепенно" tone="info">
          На этом шаге зафиксированы визуальные правила и базовые UI primitives.
          Следующий технический слой — API client, Zod-схемы и query hooks.
        </Alert>

        <section className={styles.sectionGrid}>
          {plannedSections.map((section) => (
            <Card className={styles.sectionCard} key={section} variant="muted">
              <div className={styles.cardMarker} />
              <p>{section}</p>
            </Card>
          ))}
        </section>

        <Card
          actions={<Button variant="primary">Следующий этап: API слой</Button>}
          description="Здесь появятся KPI, список писем и карточка выбранного письма."
          title="Каркас dashboard"
          variant="muted"
        >
          <EmptyState
            description="UI primitives готовы, но реальные widgets пока не подключены. Это намеренно: сначала стабилизируем основу."
            title="Данные будут подключены следующим шагом"
          />
        </Card>
      </div>
    </main>
  )
}
