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
        <Skeleton height={140} />
        <Skeleton height={72} />
        <Skeleton height={140} />
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

        <Section title="Классификация">
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
            <p className={styles.reason}>{data.classification.reason_ru}</p>
          )}
        </Section>

        <Section title="Сводка">
          <p className={styles.text}>{data.summary || 'Сводка отсутствует.'}</p>
        </Section>

        <Section title="Ключевые факты">
          {data.key_facts.length > 0 ? (
            <ul className={styles.list}>
              {data.key_facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>Ключевые факты не выделены.</p>
          )}
        </Section>

        {data.warnings.length > 0 && (
          <Section>
            <Alert title="Требует внимания" tone="warning">
              <ul className={styles.list}>
                {data.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </Alert>
          </Section>
        )}

        <Collapsible title="Вложения">
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

        <Collapsible title="Тело письма">
          <p className={styles.content}>
            {data.content || 'Текст отсутствует.'}
          </p>
        </Collapsible>

        <Collapsible title="Отладка">
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
            <Collapsible title="original_email JSON">
              <JsonViewer value={data.original_email} />
            </Collapsible>
            <Collapsible title="agent_result JSON">
              <JsonViewer value={data.agent_result} />
            </Collapsible>
          </div>
        </Collapsible>
      </div>
    </div>
  )
}
