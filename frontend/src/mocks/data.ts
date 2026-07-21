export type MockClassification = {
  status: 'classified' | 'new_project' | 'manual_review'
  class_code: string | null
  class_name_ru: string | null
  reason_ru: string | null
  confidence: number | null
  message_ru: string | null
}

export type MockAttachment = {
  attachment_id: string
  id: string
  position: number
  original_filename: string
  safe_filename: string
  filename: string
  content_type: string
  detected_content_type: string
  size: number
  sha256: string
  is_inline: boolean
  content_id: string | null
  summary: string | null
  key_facts: string[]
  processing_result: Record<string, unknown> | null
  download_url: string
  mock_content: string
}

export type MockEmailDetail = {
  id: string
  subject: string
  from: string
  content: string
  summary: string
  classification: MockClassification | null
  key_facts: string[]
  attachment_summaries: string[]
  warnings: string[]
  record_id: string
  received_at: string
  processed_at: string
  mailbox: string
  uid: string
  message_id: string | null
  pipeline_version: string
  processing_generation: number
  original_email: {
    subject: string
    from: string
    to: string[]
    cc: string[]
    bcc: string[]
    reply_to: string[]
    headers: Array<{ name: string; value: string }>
    flags: string[]
    size_bytes: number
    text_plain: string
    text_html: string
    normalized_body: string
  }
  agent_result: Record<string, unknown>
  attachments: MockAttachment[]
  raw_download_url: string
  raw_content: string
}

const sha256 = '0'.repeat(64)

const classifiedTemplates = [
  {
    classCode: '3D_PRINTERS',
    className: '3D-принтеры',
    subject: 'Подбор промышленного 3D-принтера',
    summary: 'Клиент просит подобрать промышленный 3D-принтер для прототипов.',
  },
  {
    classCode: 'CHEMISTRY',
    className: 'Химия',
    subject: 'Линия дозирования химических компонентов',
    summary: 'Запрос на оборудование для дозирования и смешивания реагентов.',
  },
  {
    classCode: 'FOUNDRY',
    className: 'Литейное производство',
    subject: 'Оснастка для литейного участка',
    summary: 'Нужно оценить комплект оборудования для литейного производства.',
  },
  {
    classCode: 'MOLD_PRINTING',
    className: 'Печать форм',
    subject: 'Печать форм для мелкосерийного производства',
    summary: 'Клиент интересуется печатью форм и сроками запуска участка.',
  },
  {
    classCode: 'PRODUCTION_LINES',
    className: 'Производственные линии',
    subject: 'Комплектация производственной линии',
    summary: 'Запрос на предварительную комплектацию производственной линии.',
  },
  {
    classCode: 'TECHNICAL_VISION',
    className: 'Техническое зрение',
    subject: 'Система технического зрения для контроля',
    summary: 'Нужна система технического зрения для контроля качества изделий.',
  },
  {
    classCode: 'OTHER_EQUIPMENT',
    className: 'Другое оборудование',
    subject: 'Подбор промышленного оборудования',
    summary:
      'Запрос относится к промышленному оборудованию вне основных классов.',
  },
]

function buildEmail(seed: {
  recordId: string
  uid: string
  receivedAt: string
  subject: string
  sender: string
  summary: string
  classification: MockClassification | null
  confidence: number | null
  attachments?: Array<{
    id: string
    filename: string
    contentType: string
    summary: string
    keyFacts: string[]
  }>
  warnings?: string[]
}): MockEmailDetail {
  const attachmentSummaries = (seed.attachments ?? []).map(
    (attachment) => `${attachment.filename}: ${attachment.summary}`,
  )
  const content = [
    `Здравствуйте. ${seed.summary}`,
    'Просим изучить запрос и подготовить коммерческое предложение.',
  ].join('\n\n')
  const processedAt = new Date(
    new Date(seed.receivedAt).getTime() + 3 * 60 * 1000,
  ).toISOString()

  return {
    id: seed.recordId,
    subject: seed.subject,
    from: seed.sender,
    content,
    summary: seed.summary,
    classification: seed.classification,
    key_facts: [
      'Требуется предварительная оценка стоимости',
      'Ожидается обратная связь в течение недели',
    ],
    attachment_summaries: attachmentSummaries,
    warnings: seed.warnings ?? [],
    record_id: seed.recordId,
    received_at: seed.receivedAt,
    processed_at: processedAt,
    mailbox: 'INBOX',
    uid: seed.uid,
    message_id: `<${seed.uid}@example.test>`,
    pipeline_version: '2',
    processing_generation: 0,
    original_email: {
      subject: seed.subject,
      from: seed.sender,
      to: ['sales@example.test'],
      cc: [],
      bcc: [],
      reply_to: [],
      headers: [
        { name: 'Message-ID', value: `<${seed.uid}@example.test>` },
        { name: 'X-Mailbox', value: 'INBOX' },
      ],
      flags: [],
      size_bytes: 4096,
      text_plain: content,
      text_html: `<p>${content.replaceAll('\n\n', '</p><p>')}</p>`,
      normalized_body: content,
    },
    agent_result: {
      summary: {
        summary_ru: seed.summary,
        classification: seed.classification,
        key_facts_ru: [
          'Требуется предварительная оценка стоимости',
          'Ожидается обратная связь в течение недели',
        ],
        attachment_summaries: attachmentSummaries,
        warnings_ru: seed.warnings ?? [],
        confidence: seed.confidence,
      },
      attachment_count: seed.attachments?.length ?? 0,
      warnings: [],
    },
    attachments: (seed.attachments ?? []).map((attachment, index) => ({
      attachment_id: attachment.id,
      id: attachment.id,
      position: index,
      original_filename: attachment.filename,
      safe_filename: attachment.filename,
      filename: attachment.filename,
      content_type: attachment.contentType,
      detected_content_type: attachment.contentType,
      size: 18_432 + index * 2048,
      sha256,
      is_inline: false,
      content_id: null,
      summary: attachment.summary,
      key_facts: attachment.keyFacts,
      processing_result: {
        summary_ru: attachment.summary,
        key_facts_ru: attachment.keyFacts,
      },
      download_url: `/api/v1/emails/${seed.recordId}/attachments/${attachment.id}/content`,
      mock_content: `Mock file: ${attachment.filename}\n${attachment.summary}\n`,
    })),
    raw_download_url: `/api/v1/emails/${seed.recordId}/raw`,
    raw_content: [
      `From: ${seed.sender}`,
      'To: sales@example.test',
      `Subject: ${seed.subject}`,
      `Message-ID: <${seed.uid}@example.test>`,
      '',
      content,
    ].join('\r\n'),
  }
}

export const mockEmails = [
  buildEmail({
    recordId: 'a'.repeat(64),
    uid: '1001',
    receivedAt: '2026-07-17T10:00:00.000Z',
    subject: 'Запрос КП на токарный станок',
    sender: 'ivan.petrov@example.test',
    summary: 'Клиент просит рассчитать поставку токарного станка с ЧПУ.',
    confidence: 0.91,
    classification: {
      status: 'classified',
      class_code: 'MACHINES',
      class_name_ru: 'Станки',
      reason_ru: 'В письме явно указан токарный станок с ЧПУ.',
      confidence: 0.91,
      message_ru: 'Запрос относится к направлению станков.',
    },
    attachments: [
      {
        id: '11111111-1111-4111-8111-111111111111',
        filename: 'technical_requirements.pdf',
        contentType: 'application/pdf',
        summary: 'Техническое задание на станок с параметрами обработки.',
        keyFacts: ['Указан диаметр обработки', 'Нужна система ЧПУ'],
      },
    ],
  }),
  buildEmail({
    recordId: 'b'.repeat(64),
    uid: '1002',
    receivedAt: '2026-07-16T14:30:00.000Z',
    subject: 'Автоматизация участка упаковки',
    sender: 'robotics@example.test',
    summary: 'Запрос на роботизированную ячейку для укладки продукции.',
    confidence: 0.84,
    classification: {
      status: 'classified',
      class_code: 'ROBOTIC_CELLS',
      class_name_ru: 'Роботизированные ячейки',
      reason_ru: 'Описана роботизированная укладка продукции.',
      confidence: 0.84,
      message_ru: 'Запрос относится к роботизированным ячейкам.',
    },
    attachments: [
      {
        id: '22222222-2222-4222-8222-222222222222',
        filename: 'layout.xlsx',
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        summary: 'План участка и производительность линии.',
        keyFacts: ['Нужно 12 циклов в минуту', 'Есть ограничения по площади'],
      },
    ],
  }),
  buildEmail({
    recordId: 'c'.repeat(64),
    uid: '1003',
    receivedAt: '2026-07-15T08:20:00.000Z',
    subject: 'Новая идея проекта',
    sender: 'new.project@example.test',
    summary: 'Письмо не относится к текущим направлениям оборудования.',
    confidence: 0.67,
    classification: {
      status: 'new_project',
      class_code: null,
      class_name_ru: null,
      reason_ru: 'Нет явной связи с поддерживаемыми классами оборудования.',
      confidence: 0.67,
      message_ru: 'Это новый проект',
    },
  }),
  buildEmail({
    recordId: 'd'.repeat(64),
    uid: '1004',
    receivedAt: '2026-07-14T16:05:00.000Z',
    subject: 'Нечитаемое вложение с запросом',
    sender: 'review@example.test',
    summary: 'Часть данных недоступна из-за проблем с вложением.',
    confidence: null,
    classification: {
      status: 'manual_review',
      class_code: null,
      class_name_ru: null,
      reason_ru: 'Важное вложение не удалось обработать надёжно.',
      confidence: null,
      message_ru: 'Требуется ручная проверка',
    },
    warnings: ['Вложение требует ручной проверки'],
    attachments: [
      {
        id: '44444444-4444-4444-8444-444444444444',
        filename: 'scan.zip',
        contentType: 'application/zip',
        summary: 'Архив не был обработан автоматически.',
        keyFacts: ['Нужно открыть вручную'],
      },
    ],
  }),
  buildEmail({
    recordId: 'e'.repeat(64),
    uid: '1005',
    receivedAt: '2026-07-14T11:40:00.000Z',
    subject: 'Комплект документов по производственной линии',
    sender: 'line.project@example.test',
    summary:
      'Клиент прислал техническое задание и планировку для расчёта производственной линии.',
    confidence: 0.88,
    classification: {
      status: 'classified',
      class_code: 'PRODUCTION_LINES',
      class_name_ru: 'Производственные линии',
      reason_ru:
        'В письме описана комплексная линия и приложены документы для расчёта.',
      confidence: 0.88,
      message_ru: 'Запрос относится к производственным линиям.',
    },
    attachments: [
      {
        id: '55555555-5555-4555-8555-555555555555',
        filename: 'technical_task.pdf',
        contentType: 'application/pdf',
        summary:
          'Техническое задание с требованиями к производительности и составу линии.',
        keyFacts: [
          'Нужна производительность 1800 изделий в час',
          'Требуется автоматическая отбраковка',
        ],
      },
      {
        id: '66666666-6666-4666-8666-666666666666',
        filename: 'workshop_layout.dwg',
        contentType: 'application/acad',
        summary:
          'Планировка цеха с зонами подвода коммуникаций и ограничениями по габаритам.',
        keyFacts: [
          'Доступная длина участка 28 метров',
          'Есть ограничение по высоте 4.2 метра',
        ],
      },
    ],
  }),
  ...Array.from({ length: 32 }, (_, index) => {
    const template = classifiedTemplates[index % classifiedTemplates.length]
    const day = 13 - Math.floor(index / 3)
    const hour = 17 - (index % 8)
    const confidence = Math.max(0.42, 0.92 - (index % 10) * 0.05)
    const isManualReview = index % 11 === 5
    const isNewProject = index % 13 === 7
    const hasAttachment = index % 3 !== 1
    const recordId = (index + 5).toString(16).padStart(64, '0').slice(-64)

    return buildEmail({
      recordId,
      uid: String(1100 + index),
      receivedAt: `2026-07-${String(day).padStart(2, '0')}T${String(hour).padStart(2, '0')}:15:00.000Z`,
      subject: `${template.subject} #${index + 1}`,
      sender: `client${index + 1}@example.test`,
      summary: template.summary,
      confidence: isManualReview ? null : confidence,
      classification: isManualReview
        ? {
            status: 'manual_review',
            class_code: null,
            class_name_ru: null,
            reason_ru: 'В mock-данных имитируется недостаток надёжных данных.',
            confidence: null,
            message_ru: 'Требуется ручная проверка',
          }
        : isNewProject
          ? {
              status: 'new_project',
              class_code: null,
              class_name_ru: null,
              reason_ru: 'Запрос не подходит под текущие направления.',
              confidence,
              message_ru: 'Это новый проект',
            }
          : {
              status: 'classified',
              class_code: template.classCode,
              class_name_ru: template.className,
              reason_ru: `Mock-классификация по признакам класса ${template.className}.`,
              confidence,
              message_ru: `Запрос относится к направлению ${template.className}.`,
            },
      warnings: isManualReview
        ? ['Mock warning: требуется ручная проверка']
        : [],
      attachments: hasAttachment
        ? [
            {
              id: `${String(index + 10).padStart(8, '0')}-aaaa-4aaa-8aaa-${String(index + 10).padStart(12, '0')}`,
              filename: `mock_attachment_${index + 1}.pdf`,
              contentType: 'application/pdf',
              summary: 'Mock-вложение с техническими требованиями.',
              keyFacts: [
                'Есть исходные требования',
                'Нужна проверка менеджера',
              ],
            },
          ]
        : [],
    })
  }),
]
