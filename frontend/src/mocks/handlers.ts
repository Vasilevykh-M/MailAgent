import { delay, http, HttpResponse } from 'msw'

import { mockEmails, type MockEmailDetail } from './data'

type Cursor = {
  received_at: string
  record_id: string
}

const requestDelayMs = 120
const maxLimit = 100
const maxStatisticsPeriodMs = 3660 * 24 * 60 * 60 * 1000
const mockAccessToken = 'mock-access-token'
const mockUser = {
  id: '00000000-0000-4000-8000-000000000001',
  username: 'admin',
}

function jsonError(error: string, status: number, requestId = 'mock-request') {
  return HttpResponse.json({ error, request_id: requestId }, { status })
}

function encodeCursor(email: MockEmailDetail): string {
  const value = JSON.stringify({
    received_at: email.received_at,
    record_id: email.record_id,
  })

  return btoa(value)
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replace(/=+$/, '')
}

function decodeCursor(value: string | null): Cursor | null {
  if (!value) {
    return null
  }

  try {
    const padded = value.replaceAll('-', '+').replaceAll('_', '/')
    const raw = JSON.parse(
      atob(padded.padEnd(Math.ceil(padded.length / 4) * 4, '=')),
    )

    if (
      typeof raw.received_at !== 'string' ||
      typeof raw.record_id !== 'string'
    ) {
      return null
    }

    return raw
  } catch {
    return null
  }
}

function byReceivedAtDesc(left: MockEmailDetail, right: MockEmailDetail) {
  const byDate =
    new Date(right.received_at).getTime() - new Date(left.received_at).getTime()

  return byDate || right.record_id.localeCompare(left.record_id)
}

function isInsideListWindow(
  email: MockEmailDetail,
  from: string | null,
  to: string | null,
) {
  const receivedAt = new Date(email.received_at).getTime()

  if (from && receivedAt < new Date(from).getTime()) {
    return false
  }

  if (to && receivedAt > new Date(to).getTime()) {
    return false
  }

  return true
}

function isInsideStatisticsWindow(
  email: MockEmailDetail,
  from: Date,
  to: Date,
) {
  const receivedAt = new Date(email.received_at)

  return receivedAt >= from && receivedAt < to
}

function toListItem(email: MockEmailDetail) {
  const confidence =
    typeof email.classification?.confidence === 'number'
      ? email.classification.confidence
      : null

  return {
    record_id: email.record_id,
    id: email.id,
    received_at: email.received_at,
    from: email.from,
    subject: email.subject,
    summary_preview: email.summary.slice(0, 500),
    attachment_count: email.attachments.length,
    confidence,
    class_code: email.classification?.class_code ?? null,
    class_name_ru: email.classification?.class_name_ru ?? null,
  }
}

function resolveEmail(recordId: string) {
  return mockEmails.find((email) => email.record_id === recordId)
}

function headersWithRequestId(request: Request) {
  return {
    'X-Request-ID': request.headers.get('X-Request-ID') || 'mock-request',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  }
}

function hasAuth(request: Request) {
  return request.headers.get('Authorization') === `Bearer ${mockAccessToken}`
}

export const handlers = [
  http.post('*/api/v1/auth/login', async ({ request }) => {
    await delay(requestDelayMs)

    const payload = (await request.json().catch(() => null)) as {
      password?: unknown
      username?: unknown
    } | null

    if (
      typeof payload?.username !== 'string' ||
      !payload.username.trim() ||
      typeof payload.password !== 'string' ||
      !payload.password
    ) {
      return jsonError('unauthorized', 401)
    }

    return HttpResponse.json(
      {
        access_token: mockAccessToken,
        expires_in: 28_800,
        token_type: 'bearer',
        user: {
          ...mockUser,
          username: payload.username.trim(),
        },
      },
      { headers: headersWithRequestId(request) },
    )
  }),

  http.get('*/api/v1/auth/me', async ({ request }) => {
    await delay(requestDelayMs)

    if (!hasAuth(request)) {
      return jsonError('unauthorized', 401)
    }

    return HttpResponse.json(mockUser, {
      headers: headersWithRequestId(request),
    })
  }),

  http.post('*/api/v1/auth/logout', async ({ request }) => {
    await delay(requestDelayMs)

    if (!hasAuth(request)) {
      return jsonError('unauthorized', 401)
    }

    return new HttpResponse(null, {
      headers: headersWithRequestId(request),
      status: 204,
    })
  }),

  http.get('*/health/live', async () => {
    await delay(requestDelayMs)

    return HttpResponse.json({ status: 'ok' })
  }),

  http.get('*/health/ready', async () => {
    await delay(requestDelayMs)

    return HttpResponse.json({ status: 'ok' })
  }),

  http.get('*/api/v1/emails', async ({ request }) => {
    await delay(requestDelayMs)

    const url = new URL(request.url)
    const rawLimit = Number(url.searchParams.get('limit') ?? '50')

    if (!Number.isInteger(rawLimit) || rawLimit < 1 || rawLimit > maxLimit) {
      return jsonError('invalid_payload', 422)
    }

    const from = url.searchParams.get('from')
    const to = url.searchParams.get('to')
    const mailbox = url.searchParams.get('mailbox')
    const cursor = decodeCursor(url.searchParams.get('cursor'))

    if (url.searchParams.get('cursor') && cursor === null) {
      return jsonError('invalid_payload', 422)
    }

    if (from && to && new Date(from).getTime() > new Date(to).getTime()) {
      return jsonError('invalid_payload', 422)
    }

    let items = [...mockEmails]
      .filter((email) => !mailbox || email.mailbox === mailbox)
      .filter((email) => isInsideListWindow(email, from, to))
      .sort(byReceivedAtDesc)

    if (cursor) {
      const cursorTime = new Date(cursor.received_at).getTime()
      items = items.filter((email) => {
        const receivedAt = new Date(email.received_at).getTime()

        return (
          receivedAt < cursorTime ||
          (receivedAt === cursorTime && email.record_id < cursor.record_id)
        )
      })
    }

    const page = items.slice(0, rawLimit)
    const hasMore = items.length > rawLimit

    return HttpResponse.json(
      {
        items: page.map(toListItem),
        next_cursor: hasMore ? encodeCursor(page[page.length - 1]) : null,
        has_more: hasMore,
      },
      { headers: headersWithRequestId(request) },
    )
  }),

  http.get('*/api/v1/statistics', async ({ request }) => {
    await delay(requestDelayMs)

    const url = new URL(request.url)
    const from = url.searchParams.get('from')
    const to = url.searchParams.get('to')
    const mailbox = url.searchParams.get('mailbox')

    if (!from || !to) {
      return jsonError('invalid_payload', 422)
    }

    const start = new Date(from)
    const end = new Date(to)

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return jsonError('invalid_payload', 422)
    }

    if (
      start >= end ||
      end.getTime() - start.getTime() > maxStatisticsPeriodMs
    ) {
      return jsonError('invalid_payload', 422)
    }

    const emails = mockEmails
      .filter((email) => !mailbox || email.mailbox === mailbox)
      .filter((email) => isInsideStatisticsWindow(email, start, end))

    const classifications = new Map<
      string,
      {
        status: string | null
        class_code: string | null
        class_name_ru: string | null
        count: number
      }
    >()

    for (const email of emails) {
      const classification = email.classification
      const key = JSON.stringify([
        classification?.status ?? null,
        classification?.class_code ?? null,
        classification?.class_name_ru ?? null,
      ])
      const current = classifications.get(key)

      if (current) {
        current.count += 1
      } else {
        classifications.set(key, {
          status: classification?.status ?? null,
          class_code: classification?.class_code ?? null,
          class_name_ru: classification?.class_name_ru ?? null,
          count: 1,
        })
      }
    }

    return HttpResponse.json(
      {
        from: start.toISOString(),
        to: end.toISOString(),
        mailbox,
        total_emails: emails.length,
        total_attachments: emails.reduce(
          (total, email) => total + email.attachments.length,
          0,
        ),
        classifications: [...classifications.values()].sort(
          (left, right) =>
            right.count - left.count ||
            (left.class_code ?? '').localeCompare(right.class_code ?? '') ||
            (left.status ?? '').localeCompare(right.status ?? ''),
        ),
      },
      { headers: headersWithRequestId(request) },
    )
  }),

  http.get('*/api/v1/emails/:recordId', async ({ params, request }) => {
    await delay(requestDelayMs)

    const recordId = String(params.recordId)
    const email = resolveEmail(recordId)

    if (!email) {
      return jsonError('not_found', 404)
    }

    return HttpResponse.json(email, { headers: headersWithRequestId(request) })
  }),

  http.get(
    '*/api/v1/emails/:recordId/attachments/:attachmentId/content',
    async ({ params, request }) => {
      await delay(requestDelayMs)

      const recordId = String(params.recordId)
      const attachmentId = String(params.attachmentId)
      const email = resolveEmail(recordId)
      const attachment = email?.attachments.find(
        (item) => item.id === attachmentId,
      )

      if (!email || !attachment) {
        return jsonError('not_found', 404)
      }

      return new HttpResponse(attachment.mock_content, {
        headers: {
          ...headersWithRequestId(request),
          'Content-Disposition': `attachment; filename="${attachment.safe_filename}"`,
          'Content-Length': String(attachment.mock_content.length),
          'Content-Type': attachment.detected_content_type,
        },
      })
    },
  ),

  http.get('*/api/v1/emails/:recordId/raw', async ({ params, request }) => {
    await delay(requestDelayMs)

    const recordId = String(params.recordId)
    const email = resolveEmail(recordId)

    if (!email) {
      return jsonError('not_found', 404)
    }

    return new HttpResponse(email.raw_content, {
      headers: {
        ...headersWithRequestId(request),
        'Content-Disposition': 'attachment; filename="message.eml"',
        'Content-Length': String(email.raw_content.length),
        'Content-Type': 'message/rfc822',
      },
    })
  }),

  http.put(
    '*/api/v1/internal/emails/:recordId',
    async ({ params, request }) => {
      await delay(requestDelayMs)

      const recordId = String(params.recordId)
      const idempotencyKey = request.headers.get('Idempotency-Key')

      if (!request.headers.get('X-API-Key')) {
        return jsonError('unauthorized', 401)
      }

      if (idempotencyKey !== recordId) {
        return jsonError('invalid_payload', 422)
      }

      const formData = await request.formData().catch(() => null)
      const payloadRaw = formData?.get('payload')
      const rawEmail = formData?.get('raw_email')

      if (typeof payloadRaw !== 'string' || !(rawEmail instanceof File)) {
        return jsonError('invalid_payload', 422)
      }

      try {
        const payload = JSON.parse(payloadRaw) as {
          record_id?: string
          processing_generation?: number
          files?: unknown[]
        }

        if (payload.record_id !== recordId) {
          return jsonError('invalid_payload', 422)
        }

        return HttpResponse.json(
          {
            record_id: recordId,
            status: 'committed',
            processing_generation: payload.processing_generation ?? 0,
            attachment_count: Array.isArray(payload.files)
              ? payload.files.length
              : 0,
            storage_verified: true,
            committed_at: new Date().toISOString(),
          },
          { headers: headersWithRequestId(request) },
        )
      } catch {
        return jsonError('invalid_payload', 422)
      }
    },
  ),
]
