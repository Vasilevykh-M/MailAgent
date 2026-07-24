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
  Collapsible,
  EmptyState,
  FileItem,
  JsonViewer,
  KeyValueTable,
  Section,
  Skeleton,
} from '../../../shared'
import {
  formatConfidence,
  formatDateTime,
  formatFileSize,
  formatNullable,
  getConfidenceTone,
} from '../../../shared'
import { ApiErrorState } from '../ApiErrorState'
import {
  getClassificationStatusLabel,
  getClassificationStatusTone,
} from './classification'

import styles from './EmailDetailPanel.module.css'

type EmailDetailPanelProps = {
  data: EmailDetail | undefined
  isLoading: boolean
  error: unknown
  isPlaceholder: boolean
  onRetry: () => void
}

type DownloadFailure = {
  error: unknown
  retry: () => Promise<void>
}

export function EmailDetailPanel({
  data,
  isLoading,
  error,
  isPlaceholder,
  onRetry,
}: EmailDetailPanelProps) {
  const [downloadFailure, setDownloadFailure] =
    useState<DownloadFailure | null>(null)

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
        <Skeleton height={140} />
        <Skeleton height={72} />
        <Skeleton height={140} />
      </div>
    )
  }

  if (error || !data) {
    return (
      <ApiErrorState
        description="Запись могла быть удалена или выбранный record_id некорректен."
        error={error}
        onRetry={onRetry}
        title="Письмо не найдено"
      />
    )
  }

  async function safelyDownload(action: () => Promise<void>) {
    setDownloadFailure(null)

    try {
      await action()
    } catch (downloadError) {
      setDownloadFailure({
        error: downloadError,
        retry: action,
      })
    }
  }

  return (
    <div className={styles.detail}>
      <header className={styles.header}>
        <div className={styles.senderBlock}>
          <span className={styles.eyebrow}>Отправитель</span>
          <p className={styles.sender}>{data.from}</p>
        </div>
        <dl className={styles.messageMeta}>
          <div>
            <dt>Получено</dt>
            <dd>{formatDateTime(data.received_at)}</dd>
          </div>
          <div>
            <dt>Mailbox</dt>
            <dd>{data.mailbox}</dd>
          </div>
        </dl>
        <Button
          className={styles.rawButton}
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
        {downloadFailure && (
          <ApiErrorState
            description="Не удалось скачать файл. Проверьте доступ к API."
            error={downloadFailure.error}
            onRetry={() => void safelyDownload(downloadFailure.retry)}
            title="Ошибка скачивания"
          />
        )}

        <Section className={styles.section} title="Классификация">
          <KeyValueTable
            items={[
              {
                key: 'status',
                label: 'Статус',
                value: (
                  <Badge
                    tone={getClassificationStatusTone(
                      data.classification?.status,
                    )}
                  >
                    {getClassificationStatusLabel(data.classification?.status)}
                  </Badge>
                ),
              },
              {
                key: 'class',
                label: 'Класс',
                value: formatNullable(data.classification?.class_name_ru),
              },
              {
                key: 'code',
                label: 'Код',
                value: formatNullable(data.classification?.class_code),
              },
              {
                key: 'confidence',
                label: 'Уверенность',
                value: (
                  <Badge
                    tone={getConfidenceTone(data.classification?.confidence)}
                  >
                    {formatConfidence(data.classification?.confidence)}
                  </Badge>
                ),
              },
            ]}
          />
          {data.classification?.reason_ru && (
            <div className={styles.reason}>
              <span>Основание</span>
              <p>{data.classification.reason_ru}</p>
            </div>
          )}
        </Section>

        <Section className={styles.section} title="Сводка">
          <p className={styles.summary}>
            {data.summary || 'Сводка отсутствует.'}
          </p>
        </Section>

        <Section className={styles.section} title="Ключевые факты">
          {data.key_facts.length > 0 ? (
            <ul className={styles.factList}>
              {data.key_facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>Ключевые факты не выделены.</p>
          )}
        </Section>

        {data.warnings.length > 0 && (
          <Section className={styles.section}>
            <Alert title="Требует внимания" tone="warning">
              <ul className={styles.list}>
                {data.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </Alert>
          </Section>
        )}

        <Collapsible className={styles.collapsible} title="Вложения">
          {data.attachments.length > 0 ? (
            <div className={styles.attachments}>
              {data.attachments.map((attachment) => (
                <FileItem
                  actions={
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
                  }
                  description={attachment.summary}
                  facts={attachment.key_facts}
                  key={attachment.id}
                  meta={`${attachment.detected_content_type} · ${formatFileSize(attachment.size)}`}
                  title={attachment.filename}
                />
              ))}
            </div>
          ) : (
            <p className={styles.muted}>Вложений нет.</p>
          )}
        </Collapsible>

        <Collapsible className={styles.collapsible} title="Тело письма">
          <p className={styles.content}>
            {data.content || 'Текст отсутствует.'}
          </p>
        </Collapsible>

        <Collapsible className={styles.collapsible} title="Отладка">
          <KeyValueTable
            items={[
              {
                key: 'record_id',
                label: 'Record ID',
                value: data.record_id,
              },
              { key: 'uid', label: 'UID', value: data.uid },
              {
                key: 'mailbox',
                label: 'Mailbox',
                value: data.mailbox,
              },
              {
                key: 'message_id',
                label: 'Message ID',
                value: formatNullable(data.message_id),
              },
              {
                key: 'pipeline',
                label: 'Pipeline',
                value: data.pipeline_version,
              },
              {
                key: 'generation',
                label: 'Generation',
                value: data.processing_generation,
              },
              {
                key: 'processed',
                label: 'Processed',
                value: formatDateTime(data.processed_at),
              },
            ]}
          />
          <div className={styles.jsonSections}>
            <Collapsible
              className={styles.nestedCollapsible}
              title="original_email JSON"
            >
              <JsonViewer value={data.original_email} />
            </Collapsible>
            <Collapsible
              className={styles.nestedCollapsible}
              title="agent_result JSON"
            >
              <JsonViewer value={data.agent_result} />
            </Collapsible>
          </div>
        </Collapsible>
      </div>
    </div>
  )
}
