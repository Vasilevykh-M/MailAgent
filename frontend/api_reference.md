# Results API для frontend dashboard

Этот документ фиксирует публичные HTTP-запросы `api-service`, которые можно
использовать при планировании frontend dashboard для обработанных писем.

## Базовая информация

- Пример base URL в локальной сети: `http://192.168.88.32:8080`.
- Read-only endpoints требуют `X-API-Key: READER_API_KEY` или
  `Authorization: Bearer READER_API_KEY`.
- Если на backend включён `ALLOW_ANONYMOUS_READER=true`, read-only endpoints
  доступны без ключа. Такой режим безопасен только в доверенной сети.
- Все ответы добавляют заголовок `X-Request-ID`.
- JSON-ответы также получают `Cache-Control: no-store` и
  `X-Content-Type-Options: nosniff`.
- Прямые MinIO/S3 URL не выдаются. Вложения и исходные `.eml` скачиваются только
  потоково через API.

## Ошибки

Формат безопасной ошибки:

```json
{
  "error": "unauthorized",
  "request_id": "request-id"
}
```

Известные коды:

- `unauthorized` — нет или неверен API key, HTTP `401`.
- `not_found` — запись, вложение или объект не найден, HTTP `404`.
- `invalid_payload` — ошибка параметров запроса, HTTP `422`.
- `generation_conflict` — конфликт поколения записи, HTTP `409`.
- `storage_unavailable` — хранилище временно недоступно, HTTP `503`.
- `internal_error` — необработанная ошибка backend, HTTP `500`.

## Получить список писем

```bash
curl -sS \
  -H "X-API-Key: $READER_API_KEY" \
  'http://192.168.88.32:8080/api/v1/emails?limit=10'
```

Endpoint:

```http
GET /api/v1/emails
```

Query параметры:

| Параметр | Тип | Обязательный | Описание |
| --- | --- | --- | --- |
| `limit` | integer | нет | Размер страницы от `1` до `100`, по умолчанию `50`. |
| `cursor` | string | нет | Opaque cursor из `next_cursor` для следующей страницы. |
| `from` | datetime | нет | Нижняя граница `received_at`. |
| `to` | datetime | нет | Верхняя граница `received_at`. |
| `mailbox` | string | нет | Почтовый ящик, например `INBOX`. |

Пример ответа:

```json
{
  "items": [
    {
      "record_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "received_at": "2026-07-17T00:00:00Z",
      "from": "sender@example.test",
      "subject": "Тема",
      "summary_preview": "Кратко",
      "attachment_count": 1,
      "confidence": 0.9
    }
  ],
  "next_cursor": "opaque_cursor_or_null",
  "has_more": true
}
```

Поля для dashboard:

- `items[].id` или `items[].record_id` — идентификатор для перехода в карточку.
- `items[].subject` — тема письма.
- `items[].from` — отправитель.
- `items[].received_at` — дата получения.
- `items[].summary_preview` — краткое описание для списка.
- `items[].attachment_count` — количество вложений.
- `items[].confidence` — уверенность итогового анализа.
- `next_cursor` и `has_more` — пагинация.

## Получить конкретное письмо

```bash
curl -sS \
  -H "X-API-Key: $READER_API_KEY" \
  'http://192.168.88.32:8080/api/v1/emails/<record_id>'
```

Endpoint:

```http
GET /api/v1/emails/{record_id}
```

Пример ответа:

```json
{
  "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "subject": "Тема",
  "from": "sender@example.test",
  "content": "Нормализованный plain-text тела письма",
  "summary": "Итог",
  "classification": {
    "status": "classified",
    "class_code": "MACHINES",
    "class_name_ru": "Станки",
    "reason_ru": "Причина классификации",
    "confidence": 0.9,
    "message_ru": "..."
  },
  "key_facts": [
    "Срок поставки до 25 июля"
  ],
  "attachment_summaries": [
    "original.pdf: коммерческое предложение"
  ],
  "warnings": [
    "Проверить срок поставки"
  ],
  "record_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "received_at": "2026-07-17T10:00:00Z",
  "processed_at": "2026-07-17T10:03:00Z",
  "mailbox": "INBOX",
  "uid": "123",
  "message_id": "<id@example.test>",
  "pipeline_version": "2",
  "processing_generation": 0,
  "original_email": {
    "subject": "Тема",
    "from": "sender@example.test",
    "to": [
      "to@example.test"
    ],
    "cc": [],
    "bcc": [],
    "reply_to": [],
    "headers": [
      {
        "name": "X-Repeat",
        "value": "one"
      }
    ],
    "flags": [],
    "size_bytes": 0,
    "text_plain": "text",
    "text_html": "<p>text</p>",
    "normalized_body": "text"
  },
  "agent_result": {},
  "attachments": [
    {
      "attachment_id": "00000000-0000-0000-0000-000000000000",
      "id": "00000000-0000-0000-0000-000000000000",
      "position": 0,
      "original_filename": "original.pdf",
      "safe_filename": "document.pdf",
      "filename": "original.pdf",
      "content_type": "application/pdf",
      "detected_content_type": "application/pdf",
      "size": 12345,
      "sha256": "hex",
      "is_inline": false,
      "content_id": null,
      "summary": "Коммерческое предложение на станок",
      "key_facts": [
        "Указан срок поставки"
      ],
      "processing_result": {},
      "download_url": "/api/v1/emails/<record_id>/attachments/<attachment_id>/content"
    }
  ],
  "raw_download_url": "/api/v1/emails/<record_id>/raw"
}
```

Поля для dashboard:

- `subject`, `from`, `received_at` — заголовок карточки.
- `content` — нормализованное текстовое тело письма.
- `summary` — итоговая сводка.
- `classification` — статус и класс обращения.
- `key_facts` — ключевые факты.
- `attachment_summaries` — сводки по вложениям.
- `warnings` — предупреждения обработки.
- `attachments` — список файлов с метаданными, сводками и ссылками скачивания.
- `raw_download_url` — ссылка на скачивание исходного `.eml`.
- `original_email` и `agent_result` — расширенные данные для технического режима.

## Статистика

```bash
curl -sS \
  -H "X-API-Key: $READER_API_KEY" \
  'http://192.168.88.32:8080/api/v1/statistics?from=2026-07-01T00:00:00Z&to=2026-08-01T00:00:00Z&mailbox=INBOX'
```

Endpoint:

```http
GET /api/v1/statistics
```

Query параметры:

| Параметр | Тип | Обязательный | Описание |
| --- | --- | --- | --- |
| `from` | datetime | да | Начало периода, timezone обязателен, граница включается. |
| `to` | datetime | да | Конец периода, timezone обязателен, граница не включается. |
| `mailbox` | string | нет | Почтовый ящик, например `INBOX`. |

Ограничения:

- `from` должен быть раньше `to`.
- Максимальный период — 10 лет.

Пример ответа:

```json
{
  "from": "2026-07-01T00:00:00Z",
  "to": "2026-08-01T00:00:00Z",
  "mailbox": "INBOX",
  "total_emails": 12,
  "total_attachments": 7,
  "classifications": [
    {
      "status": "classified",
      "class_code": "MACHINES",
      "class_name_ru": "Станки",
      "count": 9
    },
    {
      "status": "new_project",
      "class_code": null,
      "class_name_ru": null,
      "count": 3
    }
  ]
}
```

Поля для dashboard:

- `total_emails` — KPI общего количества писем.
- `total_attachments` — KPI количества вложений.
- `classifications` — данные для диаграмм распределения.
- `classifications[].status` — статус классификации.
- `classifications[].class_code` — машинный код класса.
- `classifications[].class_name_ru` — русское название класса.
- `classifications[].count` — количество писем в сегменте.

Известные статусы классификации:

- `classified` — выбран конкретный класс.
- `new_project` — письмо не относится к известным направлениям; сообщение
  содержит `Это новый проект`.
- `manual_review` — нужна ручная проверка из-за ошибок обработки или нехватки
  надёжных данных.

Известные коды классов:

- `3D_PRINTERS`
- `CHEMISTRY`
- `FOUNDRY`
- `MOLD_PRINTING`
- `ROBOTIC_CELLS`
- `PRODUCTION_LINES`
- `MACHINES`
- `TECHNICAL_VISION`
- `OTHER_EQUIPMENT`

## Скачать вложение

```bash
curl -OJ \
  -H "X-API-Key: $READER_API_KEY" \
  'http://192.168.88.32:8080/api/v1/emails/<record_id>/attachments/<attachment_id>/content'
```

Endpoint:

```http
GET /api/v1/emails/{record_id}/attachments/{attachment_id}/content
```

Ответ:

- Body — бинарный поток файла.
- `Content-Type` — значение `detected_content_type`.
- `Content-Disposition` — attachment filename.
- `Content-Length` — размер файла.

Поля для dashboard:

- Использовать `attachments[].download_url` из карточки письма.
- Показывать кнопку `Скачать вложение`.
- Не ожидать JSON-ответа.

## Скачать исходное письмо

```bash
curl -OJ \
  -H "X-API-Key: $READER_API_KEY" \
  'http://192.168.88.32:8080/api/v1/emails/<record_id>/raw'
```

Endpoint:

```http
GET /api/v1/emails/{record_id}/raw
```

Ответ:

- Body — original MIME `.eml`.
- `Content-Type` — `message/rfc822`.
- `Content-Disposition` — `message.eml`.
- `Content-Length` — размер исходного письма.

Поля для dashboard:

- Использовать `raw_download_url` из карточки письма.
- Показывать как техническое действие `Скачать исходное письмо`.
- Не ожидать JSON-ответа.

## Health checks

```bash
curl -sS 'http://192.168.88.32:8080/health/live'
curl -sS 'http://192.168.88.32:8080/health/ready'
```

Endpoints:

```http
GET /health/live
GET /health/ready
```

Успешный ответ:

```json
{
  "status": "ok"
}
```

Ответ readiness при недоступной инфраструктуре:

```json
{
  "status": "unavailable"
}
```

Использование в dashboard:

- `live` показывает, что HTTP-приложение отвечает.
- `ready` показывает, что доступны PostgreSQL и MinIO.

## Внутренний endpoint записи

Этот endpoint не предназначен для frontend dashboard, но важен для понимания
потока данных.

```bash
curl -X PUT "http://192.168.88.32:8080/api/v1/internal/emails/$RECORD_ID" \
  -H "X-API-Key: $WRITER_API_KEY" \
  -H "Idempotency-Key: $RECORD_ID" \
  -F 'payload=@payload.json;type=application/json' \
  -F 'raw_email=@message.eml;type=message/rfc822' \
  -F 'attachment_0=@document.pdf;type=application/pdf'
```

Endpoint:

```http
PUT /api/v1/internal/emails/{record_id}
```

Требования:

- `X-API-Key: WRITER_API_KEY`.
- `Idempotency-Key`, равный `record_id`.
- Multipart field `payload` с `application/json`.
- Multipart field `raw_email` с `message/rfc822`.
- Каждый файл отдельным multipart field из `payload.files[].part_name`, например
  `attachment_0`.

Успешный ответ:

```json
{
  "record_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "status": "committed",
  "processing_generation": 0,
  "attachment_count": 1,
  "storage_verified": true,
  "committed_at": "2026-07-17T10:03:00Z"
}
```

## Предварительная карта dashboard

- Список писем: `GET /api/v1/emails`.
- Детальная карточка: `GET /api/v1/emails/{record_id}`.
- KPI и графики: `GET /api/v1/statistics`.
- Скачивание вложений: `attachments[].download_url`.
- Скачивание исходного письма: `raw_download_url`.
- Индикатор состояния backend: `GET /health/ready`.
