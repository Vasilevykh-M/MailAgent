# HTTP API

Все ответы добавляют `X-Request-ID`; ошибки имеют только безопасный `error` и request ID.

## Запись

`PUT /api/v1/internal/emails/{record_id}` требует `X-API-Key: WRITER_API_KEY` и `Idempotency-Key`, равный `record_id`. Multipart содержит `payload` (`application/json`), `raw_email` (`message/rfc822`) и каждый файл отдельным полем из `payload.files[].part_name`, например `attachment_0`.

```bash
curl -X PUT "http://127.0.0.1:8080/api/v1/internal/emails/$RECORD_ID" \
  -H "X-API-Key: $WRITER_API_KEY" -H "Idempotency-Key: $RECORD_ID" \
  -F 'payload=@payload.json;type=application/json' \
  -F 'raw_email=@message.eml;type=message/rfc822' \
  -F 'attachment_0=@document.pdf;type=application/pdf'
```

Успех возвращает `record_id`, `status: committed`, generation, количество вложений, `storage_verified` и время commit.

## Чтение

В обычном режиме external endpoints используют `X-API-Key: READER_API_KEY` либо
`Authorization: Bearer READER_API_KEY`. При `ALLOW_ANONYMOUS_READER=true` все
перечисленные read-only endpoints доступны без ключа. Это открывает содержимое
писем и вложения каждому, кто может подключиться к API; включайте режим только в
доверенной сети. Write endpoint всегда требует `WRITER_API_KEY`.

- `GET /api/v1/emails?limit=50&cursor=...&from=...&to=...&mailbox=INBOX` — лёгкий список с opaque keyset cursor. Каждый элемент содержит `id` (он же `record_id`), `subject`, `from`, `received_at`, preview, количество вложений и confidence. Максимум `100`.
- `GET /api/v1/emails/{record_id}` — полная карточка письма. Верхнеуровневые поля `id`, `subject`, `from`, `received_at`, `content`, `summary`, `classification`, `key_facts`, `attachment_summaries` и `warnings` предназначены для интерфейса. `content` — нормализованный plain-text тела письма; исходные текстовая и HTML-версии остаются в `original_email`.
- В `attachments` каждый файл содержит `id`, `filename`, `summary`, `key_facts` и `download_url`. `download_url` ведёт на потоковую загрузку файла через API; MinIO URL не выдаётся.
- `GET /api/v1/emails/{record_id}/attachments/{attachment_id}/content` — поток файла.
- `GET /api/v1/emails/{record_id}/raw` — поток original MIME как `message/rfc822`.
- `GET /health/live`, `GET /health/ready` — readiness проверяет PostgreSQL и MinIO без чтения почтовых данных.
