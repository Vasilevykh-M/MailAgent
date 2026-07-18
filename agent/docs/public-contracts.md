# Публичные контракты интеграций

Core worker использует SDK Почты как Python-библиотеку, а OCR, LLM и Results API — только по HTTP. Внутренние модули других сервисов не импортируются.

- `yandex_mail.YandexMailService.from_env(path)` — `list_messages(..., status="unread")`, `read_message(uid, mailbox, mark_read=False)` и `mark_as_read(uid, mailbox)`. `MailMessage.headers` остаётся упорядоченным `list[tuple[str, str]]`; `MailMessage.raw_bytes` переносится во временный `.eml`, не в SQLite/checkpoint.
- vLLM — `GET /health`, `GET /v1/models`, `POST /v1/chat/completions`.
- OCR — `GET /health/ready`, `GET /api/v1/capabilities`, `POST /api/v1/ocr`, `POST /api/v1/documents/parse`.
- Results API — `PUT /api/v1/internal/emails/{record_id}`. Аутентификация: writer `X-API-Key`; обязательны `Idempotency-Key: record_id` и `X-Request-ID`. Multipart содержит JSON `payload`, `raw_email` и именованные parts `attachment_N`. Успех допустим только при `status: committed` и `storage_verified: true`.

У агента ограничены timeout/retry. Он повторяет transport errors, `408`, `425`, `429` и `5xx` с тем же record ID; другие `4xx` — controlled permanent error. Содержимое писем, filenames, bytes, ключи и payload не попадают в логи.

## Классификация итогового анализа

Results API получает классификацию в гибком объекте
`agent_result.summary.classification`; `schema_version` и схема базы для этого не
меняются. Объект содержит `status`, `class_code`, `class_name_ru`, `reason_ru`,
`confidence` и `message_ru`.

Статус `classified` содержит один из кодов `3D_PRINTERS`, `CHEMISTRY`, `FOUNDRY`,
`MOLD_PRINTING`, `ROBOTIC_CELLS`, `PRODUCTION_LINES`, `MACHINES`,
`TECHNICAL_VISION`, `OTHER_EQUIPMENT` и соответствующее русское название. Итоговый
анализ использует тему, нормализованное тело, цепочку пересылки, текст и сводки
вложений, включая сведения о недоступных вложениях.

`OTHER_EQUIPMENT` допустим только для явно промышленного оборудования или запчастей,
которые не относятся к специализированным классам. Если предмет письма не относится
ни к одному направлению, используется `new_project` с `class_code: null`,
`class_name_ru: null` и точным `message_ru: "Это новый проект"`. Ошибка обработки,
сбой LLM или недостаток надёжных данных из-за недоступного вложения приводит к
`manual_review`, также с null-классом, а не к `new_project`.
