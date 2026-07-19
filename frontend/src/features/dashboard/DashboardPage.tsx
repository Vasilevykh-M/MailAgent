import { apiConfig } from '../../api/config'

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
          <p className={styles.eyebrow}>Mail Agent</p>
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

        <section className={styles.sectionGrid}>
          {plannedSections.map((section) => (
            <article className={styles.sectionCard} key={section}>
              <div className={styles.cardMarker} />
              <p>{section}</p>
            </article>
          ))}
        </section>
      </div>
    </main>
  )
}
