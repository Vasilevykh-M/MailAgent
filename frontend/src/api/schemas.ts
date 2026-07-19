import { z } from 'zod'

const unknownRecordSchema = z.record(z.string(), z.unknown())

export const apiErrorSchema = z.object({
  error: z.string(),
  request_id: z.string(),
})

export const classificationSchema = z.object({
  status: z.string().optional().nullable(),
  class_code: z.string().optional().nullable(),
  class_name_ru: z.string().optional().nullable(),
  reason_ru: z.string().optional().nullable(),
  confidence: z.number().optional().nullable(),
  message_ru: z.string().optional().nullable(),
})

export const emailListItemSchema = z.object({
  record_id: z.string(),
  id: z.string(),
  received_at: z.string(),
  from: z.string(),
  subject: z.string(),
  summary_preview: z.string(),
  attachment_count: z.number().int().nonnegative(),
  confidence: z.number().nullable(),
})

export const emailListResponseSchema = z.object({
  items: z.array(emailListItemSchema),
  next_cursor: z.string().nullable(),
  has_more: z.boolean(),
})

export const classificationStatisticsItemSchema = z.object({
  status: z.string().nullable(),
  class_code: z.string().nullable(),
  class_name_ru: z.string().nullable(),
  count: z.number().int().nonnegative(),
})

export const statisticsResponseSchema = z.object({
  from: z.string(),
  to: z.string(),
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
  attachment_id: z.string(),
  id: z.string(),
  position: z.number().int().nonnegative(),
  original_filename: z.string(),
  safe_filename: z.string(),
  filename: z.string(),
  content_type: z.string(),
  detected_content_type: z.string(),
  size: z.number().int().nonnegative(),
  sha256: z.string(),
  is_inline: z.boolean(),
  content_id: z.string().nullable(),
  summary: z.string().nullable(),
  key_facts: z.array(z.string()),
  processing_result: unknownRecordSchema.nullable(),
  download_url: z.string(),
})

export const emailDetailSchema = z.object({
  id: z.string(),
  subject: z.string(),
  from: z.string(),
  content: z.string(),
  summary: z.string(),
  classification: classificationSchema.nullable(),
  key_facts: z.array(z.string()),
  attachment_summaries: z.array(z.string()),
  warnings: z.array(z.string()),
  record_id: z.string(),
  received_at: z.string(),
  processed_at: z.string(),
  mailbox: z.string(),
  uid: z.string(),
  message_id: z.string().nullable(),
  pipeline_version: z.string(),
  processing_generation: z.number().int().nonnegative(),
  original_email: originalEmailSchema,
  agent_result: unknownRecordSchema,
  attachments: z.array(attachmentSchema),
  raw_download_url: z.string(),
})

export const healthResponseSchema = z.object({
  status: z.string(),
})
