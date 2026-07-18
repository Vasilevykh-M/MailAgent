# Mail Agent Results API

`api-service` — самостоятельный FastAPI-сервис для подтверждённого хранения результатов обработки писем. Worker передаёт ему только HTTP multipart-запрос: структурированные данные, исходный `.eml` и вложения. Сервис сохраняет metadata и результат в PostgreSQL, а бинарные объекты — в закрытый MinIO bucket.

## Быстрый запуск

Из корня репозитория подготовьте локальные секреты вне Git и запустите инфраструктуру:

```bash
cp .env.infrastructure.example .env
# Заполните POSTGRES_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD,
# WRITER_API_KEY и READER_API_KEY. Для read-only API без ключа в доверенной
# сети задайте ALLOW_ANONYMOUS_READER=true.
make infra-up
make health-data
```

`api-service` запускает Alembic и создание current/previous/future monthly partitions явно в своей командной строке. Повторное применение миграций безопасно:

```bash
make api-migrate
docker compose exec api-service .venv/bin/mail-results-partitions
```

Для локальной разработки без Docker:

```bash
cd api-service
uv sync --extra dev --python 3.11
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Настройки перечислены в [.env.example](.env.example); рабочий `.env` не создаётся и не добавляется в Git.

## Гарантии

- `PUT /api/v1/internal/emails/{record_id}` принимает `payload`, `raw_email` и именованные `attachment_N` multipart parts.
- Одинаковые `record_id`, generation и payload возвращают idempotent `committed`; более старое generation и другой payload того же generation получают controlled `409`.
- Файлы проходят потоковую SHA-256/size-проверку, upload и `HEAD` до PostgreSQL transaction. При сбое БД загруженные, но не опубликованные объекты недоступны read API.
- `email_locator` сначала определяет receipt timestamp, после чего detail query обращается к одной monthly partition.
- Read-only API требует отдельный reader key, кроме явно включённого режима `ALLOW_ANONYMOUS_READER=true`.
  Все бинарные загрузки идут потоково через API, прямых MinIO URL нет.

Подробнее: [архитектура](docs/architecture.md), [HTTP API](docs/api.md), [эксплуатация](docs/operations.md).
