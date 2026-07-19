import { Download, FileDown } from 'lucide-react'
import { useState } from 'react'

import {
  downloadAttachment,
  downloadRawEmail,
  type EmailDetail,
} from '../../../api'
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  JsonViewer,
} from '../../../shared'
import {
  formatConfidence,
  formatDateTime,
  formatFileSize,
  formatNullable,
  getConfidenceTone,
} from '../../../shared'
import {
  getClassificationStatusLabel,
  getClassificationStatusTone,
} from './classification'

import styles from './EmailDetailPanel.module.css'

type EmailDetailPanelProps = {
  data: EmailDetail | undefined
  isLoading: boolean
  isError: boolean
  isPlaceholder: boolean
}

export function EmailDetailPanel({
  data,
  isLoading,
  isError,
  isPlaceholder,
}: EmailDetailPanelProps) {
  const [downloadError, setDownloadError] = useState<string | null>(null)

  if (isPlaceholder) {
    return (
      <Card title="Карточка письма" variant="muted">
        <EmptyState
          description="Выберите письмо в списке, чтобы увидеть summary, classification, warnings, content и attachments."
          title="Письмо не выбрано"
        />
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card title="Карточка письма" variant="muted">
        <div className={styles.skeletonStack}>
          <div className={styles.skeletonLarge} />
          <div className={styles.skeletonSmall} />
          <div className={styles.skeletonLarge} />
        </div>
      </Card>
    )
  }

  if (isError || !data) {
    return (
      <Card title="Карточка письма" variant="muted">
        <EmptyState
          description="Запись могла быть удалена или выбранный record_id некорректен."
          title="Письмо не найдено"
        />
      </Card>
    )
  }

  async function safelyDownload(action: () => Promise<void>) {
    setDownloadError(null)

    try {
      await action()
    } catch {
      setDownloadError('Не удалось скачать файл. Проверьте доступ к API.')
    }
  }

  return (
    <Card
      actions={
        <Button
          onClick={() =>
            void safelyDownload(() => downloadRawEmail(data.raw_download_url))
          }
          variant="secondary"
        >
          <FileDown aria-hidden="true" size={16} />
          Скачать .eml
        </Button>
      }
      description={`${data.from} · ${formatDateTime(data.received_at)}`}
      title={data.subject || 'Без темы'}
      variant="muted"
    >
      <div className={styles.stack}>
        {downloadError && (
          <Alert title="Ошибка скачивания" tone="danger">
            {downloadError}
          </Alert>
        )}

        {data.warnings.length > 0 && (
          <Alert title="Предупреждения обработки" tone="warning">
            <ul className={styles.list}>
              {data.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </Alert>
        )}

        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>Классификация</h3>
          </div>
          <div className={styles.classificationGrid}>
            <Metric className={styles.classificationMetric} label="Статус">
              <Badge
                tone={getClassificationStatusTone(data.classification?.status)}
              >
                {getClassificationStatusLabel(data.classification?.status)}
              </Badge>
            </Metric>
            <Metric className={styles.classificationMetric} label="Класс">
              {formatNullable(data.classification?.class_name_ru)}
            </Metric>
            <Metric className={styles.classificationMetric} label="Код">
              {formatNullable(data.classification?.class_code)}
            </Metric>
            <Metric className={styles.classificationMetric} label="Уверенность">
              <Badge tone={getConfidenceTone(data.classification?.confidence)}>
                {formatConfidence(data.classification?.confidence)}
              </Badge>
            </Metric>
          </div>
          {data.classification?.reason_ru && (
            <p className={styles.reason}>{data.classification.reason_ru}</p>
          )}
        </section>

        <section className={styles.section}>
          <h3>Сводка</h3>
          <p className={styles.text}>{data.summary || 'Сводка отсутствует.'}</p>
        </section>

        <section className={styles.section}>
          <h3>Ключевые факты</h3>
          {data.key_facts.length > 0 ? (
            <ul className={styles.list}>
              {data.key_facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>Ключевые факты не выделены.</p>
          )}
        </section>

        <section className={styles.section}>
          <h3>Тело письма</h3>
          <p className={styles.content}>
            {data.content || 'Текст отсутствует.'}
          </p>
        </section>

        <section className={styles.section}>
          <h3>Сводки вложений</h3>
          {data.attachment_summaries.length > 0 ? (
            <ul className={styles.list}>
              {data.attachment_summaries.map((summary) => (
                <li key={summary}>{summary}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>Сводки вложений отсутствуют.</p>
          )}
        </section>

        <section className={styles.section}>
          <h3>Вложения</h3>
          {data.attachments.length > 0 ? (
            <div className={styles.attachments}>
              {data.attachments.map((attachment) => (
                <article className={styles.attachment} key={attachment.id}>
                  <div>
                    <p className={styles.attachmentTitle}>
                      {attachment.filename}
                    </p>
                    <p className={styles.muted}>
                      {attachment.detected_content_type} ·{' '}
                      {formatFileSize(attachment.size)}
                    </p>
                    {attachment.summary && (
                      <p className={styles.text}>{attachment.summary}</p>
                    )}
                  </div>
                  <Button
                    onClick={() =>
                      void safelyDownload(() =>
                        downloadAttachment(
                          attachment.download_url,
                          attachment.safe_filename,
                        ),
                      )
                    }
                    variant="secondary"
                  >
                    <Download aria-hidden="true" size={16} />
                    Скачать
                  </Button>
                </article>
              ))}
            </div>
          ) : (
            <p className={styles.muted}>Вложений нет.</p>
          )}
        </section>

        <details className={styles.technical}>
          <summary>Технические данные</summary>
          <dl>
            <Metric label="Record ID">{data.record_id}</Metric>
            <Metric label="UID">{data.uid}</Metric>
            <Metric label="Mailbox">{data.mailbox}</Metric>
            <Metric label="Message ID">
              {formatNullable(data.message_id)}
            </Metric>
            <Metric label="Pipeline">{data.pipeline_version}</Metric>
            <Metric label="Generation">{data.processing_generation}</Metric>
            <Metric label="Processed">
              {formatDateTime(data.processed_at)}
            </Metric>
          </dl>
          <div className={styles.jsonSections}>
            <details>
              <summary>original_email JSON</summary>
              <JsonViewer value={data.original_email} />
            </details>
            <details>
              <summary>agent_result JSON</summary>
              <JsonViewer value={data.agent_result} />
            </details>
          </div>
        </details>
      </div>
    </Card>
  )
}

type MetricProps = {
  className?: string
  label: string
  children: React.ReactNode
}

function Metric({ className = '', label, children }: MetricProps) {
  return (
    <div className={`${styles.metric} ${className}`}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}
