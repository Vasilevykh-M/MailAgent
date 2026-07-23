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

## Аутентификация

`POST /api/v1/auth/login` публичен. Он принимает username и password и возвращает
opaque token единственный раз. Для неизвестного пользователя, неверного пароля и
отключённого пользователя API возвращает одинаковый безопасный `401`.

```bash
curl -X POST http://127.0.0.1:8080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"replace-with-a-strong-secret"}'
```

```json
{
  "access_token": "opaque-session-token",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {"id": "uuid", "username": "admin"}
}
```

`GET /api/v1/auth/me` требует `Authorization: Bearer <access-token>` и возвращает
только `id` и `username`. `POST /api/v1/auth/logout` с тем же заголовком отвечает
`204 No Content` и отзывает именно эту сессию. Reader key не является
пользовательской сессией и не работает для этих маршрутов.

```bash
curl http://127.0.0.1:8080/api/v1/auth/me \
  -H 'Authorization: Bearer <access-token>'
curl -X POST http://127.0.0.1:8080/api/v1/auth/logout \
  -H 'Authorization: Bearer <access-token>'
```

## Чтение

В обычном режиме external endpoints принимают действующую пользовательскую
`Authorization: Bearer <access-token>` сессию, `X-API-Key: READER_API_KEY` либо
`Authorization: Bearer READER_API_KEY`. При `ALLOW_ANONYMOUS_READER=true` все
перечисленные read-only endpoints доступны без ключа. Это открывает содержимое
писем и вложения каждому, кто может подключиться к API; включайте режим только в
доверенной сети. Write endpoint всегда требует только `WRITER_API_KEY`.

Для браузерного frontend задайте `CORS_ALLOWED_ORIGINS` в корневом `.env`,
например `http://localhost:4173` или несколько origin через запятую. API отвечает
на CORS только для перечисленных origin, разрешает все HTTP-методы и заголовки и
отдаёт `Content-Disposition` для скачиваемых вложений. Явное значение `*`
открывает CORS для любых origin; используйте его только осознанно, особенно вместе
с `ALLOW_ANONYMOUS_READER=true`. CORS не отменяет проверку `WRITER_API_KEY` для
записи.

- `GET /api/v1/emails?limit=50&cursor=...&from=...&to=...&mailbox=INBOX` — лёгкий список с opaque keyset cursor. Каждый элемент содержит `id` (он же `record_id`), `subject`, `from`, `received_at`, preview, количество вложений, confidence, а также `class_code` и `class_name_ru`. Поля классификации всегда присутствуют: их значениями являются строка либо `null`, если письмо ещё не классифицировано или результат классификации некорректен. Максимум `100`.
- `GET /api/v1/emails/{record_id}` — полная карточка письма. Верхнеуровневые поля `id`, `subject`, `from`, `received_at`, `content`, `summary`, `classification`, `key_facts`, `attachment_summaries` и `warnings` предназначены для интерфейса. `content` — нормализованный plain-text тела письма; исходные текстовая и HTML-версии остаются в `original_email`.
- В `attachments` каждый файл содержит `id`, `filename`, `summary`, `key_facts` и `download_url`. `download_url` ведёт на потоковую загрузку файла через API; MinIO URL не выдаётся.
- `GET /api/v1/statistics?from=2026-07-01T00:00:00Z&to=2026-08-01T00:00:00Z&mailbox=INBOX` — статистика за период: `total_emails`, `total_attachments` и `classifications` с `status`, кодом, русским названием класса и количеством. `from` включается, `to` не включается; оба значения обязаны содержать timezone, максимальный период — 10 лет.
- `GET /api/v1/emails/{record_id}/attachments/{attachment_id}/content` — поток файла.
- `GET /api/v1/emails/{record_id}/raw` — поток original MIME как `message/rfc822`.
- `GET /health/live`, `GET /health/ready` — readiness проверяет PostgreSQL и MinIO без чтения почтовых данных.
