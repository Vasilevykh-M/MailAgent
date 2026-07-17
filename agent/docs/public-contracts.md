# Публичные контракты интеграций

Агент не импортирует внутренние модули сервисов и не реализует IMAP или API Яндекс Диска самостоятельно.

- `yandex_mail.YandexMailService.from_env(path)` — `list_messages(..., status="unread", limit, offset)`, `read_message(uid, mailbox, mark_read=False)` и `mark_as_read(uid, mailbox)`. `MailMessage.headers` — упорядоченный `list[tuple[str, str]]`, поэтому повторяющиеся заголовки сохраняются.
- `yandex_drive.YandexDriveService.from_env(path)` — `get_metadata`, `download_file_to`, `upload_file` и `upload_bytes`. Метаданные содержат `md5`, `sha256`, `modified` и `size`.
- vLLM — `GET /health`, `GET /v1/models`, `POST /v1/chat/completions`; локальные изображения передаются только как Data URL JPEG/PNG/WebP.
- OCR — `GET /health/ready`, `GET /api/v1/capabilities`, `POST /api/v1/ocr`, `POST /api/v1/documents/parse`. Модели, языки, форматы и лимиты берутся только из `capabilities`.

Все четыре внешних компонента остаются самостоятельными. Core запускается одним процессом и использует Mail/Drive как Python-библиотеки; LLM и OCR доступны по HTTP и могут находиться на других устройствах.
