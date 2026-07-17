# Mail Agent

Mail Agent обрабатывает непрочитанные сообщения Яндекс Почты и сохраняет их результат через независимый Results API. Core worker, OCR, LLM и Results API остаются самостоятельными компонентами; сервисы не используют внутренние Python-импорты друг друга.

```text
Яндекс Почта → mail-agent → OCR / LLM → Results API
                                           ├─ PostgreSQL
                                           └─ MinIO
                                     → confirmed commit → \Seen
```

В PostgreSQL хранятся metadata, ordered headers, plain/HTML body, нормализованный текст и структурированный результат. Оригинальный `.eml` и вложения хранятся в закрытом MinIO bucket. Excel, Markdown-отчёты и Яндекс Диск не используются в активном потоке.

## Быстрый старт

```bash
cp .env.infrastructure.example .env
# Заполните локально POSTGRES_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD,
# WRITER_API_KEY и READER_API_KEY; не добавляйте .env в Git.
make infra-up
make health-data

cp agent/config.example.yaml agent/config.yaml
cp yandex/mail/.env.example yandex/mail/.env
export RESULTS_API_KEY="$WRITER_API_KEY"
make install PROFILE=core
make auth-mail
make once
```

`agent/.env.example` содержит names переменных worker; перед запуском экспортируйте нужные значения в окружение. Не используйте один файл `.env` одновременно для Compose и worker без явной загрузки окружения.

## Компоненты

| Каталог | Назначение |
| --- | --- |
| [`agent/`](agent/README.md) | Worker, SQLite-state, LangGraph и локальная панель. |
| [`api-service/`](api-service/README.md) | FastAPI, PostgreSQL schema/partitions и MinIO adapter. |
| [`ocr-service/`](ocr-service/README.md) | Независимый PaddleOCR сервис. |
| [`llm-service/`](llm-service/README.md) | Независимый Qwen/vLLM сервис. |
| [`yandex/mail/`](yandex/mail/README.md) | SDK Яндекс Почты. |

## Основные команды

```bash
make infra-up
make infra-down
make infra-status
make api-migrate
make api-test
make api-lint
make api-typecheck
make health-data
make test
make lint
make typecheck
```

Не добавляйте рабочие OAuth/S3/API keys, MIME-файлы, вложения или volumes в Git. Для production API требуется TLS reverse proxy, private database/object storage и регулярные PostgreSQL/MinIO backups; детали — в [operations](api-service/docs/operations.md).
