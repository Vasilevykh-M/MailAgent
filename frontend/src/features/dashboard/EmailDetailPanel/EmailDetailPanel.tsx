import { Download, FileDown } from 'lucide-react'
import { useState } from 'react'

import {
  downloadAttachment,
  downloadRawEmail,
  type EmailDetail,
} from '../../../api'
import { Alert, Badge, Button, EmptyState, JsonViewer } from '../../../shared'
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
      <EmptyState
        description="Выберите письмо в списке, чтобы увидеть summary, classification, warnings, content и attachments."
        title="Письмо не выбрано"
      />
    )
  }

  if (isLoading) {
    return (
      <div className={styles.skeletonStack}>
        <div className={styles.skeletonLarge} />
        <div className={styles.skeletonSmall} />
        <div className={styles.skeletonLarge} />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <EmptyState
        description="Запись могла быть удалена или выбранный record_id некорректен."
        title="Письмо не найдено"
      />
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
    <div className={styles.detail}>
      <header className={styles.header}>
        <p className={styles.meta}>
          {data.from} · {formatDateTime(data.received_at)}
        </p>
        <Button
          onClick={() =>
            void safelyDownload(() => downloadRawEmail(data.raw_download_url))
          }
          variant="secondary"
        >
          <FileDown aria-hidden="true" size={16} />
          Скачать .eml
        </Button>
      </header>
      <div className={styles.stack}>
        {downloadError && (
          <Alert title="Ошибка скачивания" tone="danger">
            {downloadError}
          </Alert>
        )}

        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>Классификация</h3>
          </div>
          <dl className={styles.classificationTable}>
            <Metric label="Статус">
              <Badge
                tone={getClassificationStatusTone(data.classification?.status)}
              >
                {getClassificationStatusLabel(data.classification?.status)}
              </Badge>
            </Metric>
            <Metric label="Класс">
              {formatNullable(data.classification?.class_name_ru)}
            </Metric>
            <Metric label="Код">
              {formatNullable(data.classification?.class_code)}
            </Metric>
            <Metric label="Уверенность">
              <Badge tone={getConfidenceTone(data.classification?.confidence)}>
                {formatConfidence(data.classification?.confidence)}
              </Badge>
            </Metric>
          </dl>
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

        {data.warnings.length > 0 && (
          <section className={styles.section}>
            <Alert title="Требует внимания" tone="warning">
              <ul className={styles.list}>
                {data.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </Alert>
          </section>
        )}

        <CollapsibleSection title="Вложения">
          {data.attachments.length > 0 ? (
            <div className={styles.attachments}>
              {data.attachments.map((attachment) => (
                <article className={styles.attachment} key={attachment.id}>
                  <div className={styles.attachmentContent}>
                    <div className={styles.attachmentHeader}>
                      <p className={styles.attachmentTitle}>
                        {attachment.filename}
                      </p>
                      <span>
                        {attachment.detected_content_type} ·{' '}
                        {formatFileSize(attachment.size)}
                      </span>
                    </div>
                    {attachment.summary && (
                      <div className={styles.attachmentSummary}>
                        <span>{attachment.summary}</span>
                      </div>
                    )}
                    {attachment.key_facts.length > 0 && (
                      <div className={styles.attachmentSummary}>
                        <p>Ключевые факты</p>
                        <ul className={styles.attachmentFacts}>
                          {attachment.key_facts.map((fact) => (
                            <li key={fact}>{fact}</li>
                          ))}
                        </ul>
                      </div>
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
        </CollapsibleSection>

        <CollapsibleSection title="Тело письма">
          <p className={styles.content}>
            {data.content || 'Текст отсутствует.'}
          </p>
        </CollapsibleSection>

        <details className={styles.technical}>
          <summary>Отладка</summary>
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
    </div>
  )
}

type CollapsibleSectionProps = {
  title: string
  children: React.ReactNode
}

function CollapsibleSection({ title, children }: CollapsibleSectionProps) {
  return (
    <details className={styles.collapsible}>
      <summary>{title}</summary>
      <div className={styles.collapsibleBody}>{children}</div>
    </details>
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
