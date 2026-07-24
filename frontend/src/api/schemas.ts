import { z } from 'zod'

const unknownRecordSchema = z.record(z.string(), z.unknown())
const nonEmptyStringSchema = z.string().min(1)
const isoDateTimeSchema = z.iso.datetime({ offset: true })
const confidenceSchema = z.number().min(0).max(1)
const nullableIsoDateTimeSchema = isoDateTimeSchema.nullable().optional()
const nullableMailboxSchema = z.string().trim().min(1).nullable().optional()

function validateDateRange(
  value: { from?: string | null; to?: string | null },
  context: z.RefinementCtx,
) {
  if (
    value.from &&
    value.to &&
    new Date(value.from).getTime() > new Date(value.to).getTime()
  ) {
    context.addIssue({
      code: 'custom',
      message: '`from` must not be later than `to`',
      path: ['to'],
    })
  }
}

export const apiDownloadPathSchema = z.string().refine((value) => {
  try {
    const baseUrl = 'https://results-api.invalid'
    const url = new URL(value, baseUrl)

    return (
      value.startsWith('/api/v1/emails/') &&
      !value.startsWith('//') &&
      url.origin === baseUrl &&
      url.pathname.startsWith('/api/v1/emails/')
    )
  } catch {
    return false
  }
}, 'Expected a relative Results API email download path')

export const apiErrorSchema = z.object({
  error: nonEmptyStringSchema,
  request_id: nonEmptyStringSchema,
})

export const currentUserSchema = z.object({
  id: nonEmptyStringSchema,
  username: nonEmptyStringSchema,
})

export const loginPayloadSchema = z.object({
  username: z.string().trim().min(1),
  password: z.string().min(1),
})

export const loginResponseSchema = z.object({
  access_token: nonEmptyStringSchema,
  token_type: z.literal('bearer'),
  expires_in: z.number().int().positive(),
  user: currentUserSchema,
})

export const classificationSchema = z.object({
  status: z.string().optional().nullable(),
  class_code: z.string().optional().nullable(),
  class_name_ru: z.string().optional().nullable(),
  reason_ru: z.string().optional().nullable(),
  confidence: confidenceSchema.optional().nullable(),
  message_ru: z.string().optional().nullable(),
})

export const emailListItemSchema = z.object({
  record_id: nonEmptyStringSchema,
  id: nonEmptyStringSchema,
  received_at: isoDateTimeSchema,
  from: z.string(),
  subject: z.string(),
  summary_preview: z.string(),
  attachment_count: z.number().int().nonnegative(),
  confidence: confidenceSchema.nullable(),
  class_code: z.string().optional().nullable(),
  class_name_ru: z.string().optional().nullable(),
})

export const emailListResponseSchema = z
  .object({
    items: z.array(emailListItemSchema),
    next_cursor: z.string().min(1).nullable(),
    has_more: z.boolean(),
  })
  .superRefine((value, context) => {
    if (value.has_more && !value.next_cursor) {
      context.addIssue({
        code: 'custom',
        message: '`next_cursor` is required when `has_more` is true',
        path: ['next_cursor'],
      })
    }
  })

export const classificationStatisticsItemSchema = z.object({
  status: z.string().nullable(),
  class_code: z.string().nullable(),
  class_name_ru: z.string().nullable(),
  count: z.number().int().nonnegative(),
})

export const statisticsResponseSchema = z.object({
  from: isoDateTimeSchema,
  to: isoDateTimeSchema,
  mailbox: z.string().nullable(),
  total_emails: z.number().int().nonnegative(),
  total_attachments: z.number().int().nonnegative(),
  classifications: z.array(classificationStatisticsItemSchema),
})

export const originalEmailSchema = z.object({
  subject: z.string(),
  from: z.string(),
  to: z.array(z.string()),
  cc: z.array(z.string()),
  bcc: z.array(z.string()),
  reply_to: z.array(z.string()),
  headers: z.array(
    z.object({
      name: z.string(),
      value: z.string(),
    }),
  ),
  flags: z.array(z.string()),
  size_bytes: z.number().int().nonnegative(),
  text_plain: z.string(),
  text_html: z.string(),
  normalized_body: z.string(),
})

export const attachmentSchema = z.object({
  attachment_id: nonEmptyStringSchema,
  id: nonEmptyStringSchema,
  position: z.number().int().nonnegative(),
  original_filename: z.string(),
  safe_filename: z.string(),
  filename: z.string(),
  content_type: z.string(),
  detected_content_type: z.string(),
  size: z.number().int().nonnegative(),
  sha256: z.string().regex(/^[a-f0-9]{64}$/i),
  is_inline: z.boolean(),
  content_id: z.string().nullable(),
  summary: z.string().nullable(),
  key_facts: z.array(z.string()),
  processing_result: unknownRecordSchema.nullable(),
  download_url: apiDownloadPathSchema,
})

export const emailDetailSchema = z.object({
  id: nonEmptyStringSchema,
  subject: z.string(),
  from: z.string(),
  content: z.string(),
  summary: z.string(),
  classification: classificationSchema.nullable(),
  key_facts: z.array(z.string()),
  attachment_summaries: z.array(z.string()),
  warnings: z.array(z.string()),
  record_id: nonEmptyStringSchema,
  received_at: isoDateTimeSchema,
  processed_at: isoDateTimeSchema,
  mailbox: z.string(),
  uid: z.string(),
  message_id: z.string().nullable(),
  pipeline_version: z.string(),
  processing_generation: z.number().int().nonnegative(),
  original_email: originalEmailSchema,
  agent_result: unknownRecordSchema,
  attachments: z.array(attachmentSchema),
  raw_download_url: apiDownloadPathSchema,
})

export const healthResponseSchema = z.object({
  status: nonEmptyStringSchema,
})

export const emailListParamsSchema = z
  .object({
    limit: z.number().int().min(1).max(100).optional(),
    cursor: z.string().min(1).nullable().optional(),
    from: nullableIsoDateTimeSchema,
    to: nullableIsoDateTimeSchema,
    mailbox: nullableMailboxSchema,
  })
  .superRefine(validateDateRange)

export const statisticsParamsSchema = z
  .object({
    from: isoDateTimeSchema.nullable(),
    to: isoDateTimeSchema.nullable(),
    mailbox: nullableMailboxSchema,
  })
  .superRefine(validateDateRange)
