# Mail Agent Results API

`api-service` — самостоятельный FastAPI-сервис для подтверждённого хранения результатов обработки писем. Worker передаёт ему только HTTP multipart-запрос: структурированные данные, исходный `.eml` и вложения. Сервис сохраняет metadata и результат в PostgreSQL, а бинарные объекты — в закрытый MinIO bucket.

## Быстрый запуск

Из корня репозитория подготовьте локальные секреты вне Git и запустите инфраструктуру:

```bash
cp .env.infrastructure.example .env
# Заполните POSTGRES_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD,
# WRITER_API_KEY и READER_API_KEY. Для browser-авторизации также задайте
# AUTH_ADMIN_USERNAME и AUTH_ADMIN_PASSWORD в secret storage. Для read-only API
# без ключа в доверенной сети задайте ALLOW_ANONYMOUS_READER=true. Для frontend
# preview добавьте CORS_ALLOWED_ORIGINS=http://localhost:4173.
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

## Аутентификация администратора

Для первого администратора задайте обе переменные окружения (либо поместите их в
локальный `api-service/.env`, не добавляя файл в Git):

```bash
export AUTH_ADMIN_USERNAME=admin
export AUTH_ADMIN_PASSWORD='replace-with-a-strong-secret'
uv run uvicorn app.main:app
```

На старте после применённых Alembic migrations сервис создаёт администратора или
синхронизирует его пароль. Повторный старт не создаёт дубликат. Изменение
`AUTH_ADMIN_PASSWORD` с последующим рестартом меняет пароль и отзывает активные
сессии пользователя; удаление обеих переменных не удаляет существующего
пользователя. Если задана только одна из двух переменных, запуск завершается
ошибкой конфигурации. Пароли хранятся только как Argon2id hashes; передавайте их
через secret storage и никогда не коммитьте в Git.

`POST /api/v1/auth/login` принимает JSON с `username` и `password`, возвращая
opaque Bearer token на 8 часов по умолчанию. Передавайте его как
`Authorization: Bearer <access-token>` для `/api/v1/auth/me` и read-only API;
`POST /api/v1/auth/logout` отзывает текущую сессию. Срок жизни, объём случайного
токена и retention отозванных сессий заданы в `.env.example`.

Технический `READER_API_KEY` сохраняет доступ к read-only API через
`X-API-Key` либо `Authorization: Bearer`; `WRITER_API_KEY` остаётся единственным
способом записи. `ALLOW_ANONYMOUS_READER=true` отменяет вход только для
read-only маршрутов и не открывает internal write API.

Для ручного управления пользователями пароль вводится только интерактивно:

```bash
uv run mail-results-users create --username admin
uv run mail-results-users set-password --username admin
uv run mail-results-users activate --username admin
uv run mail-results-users deactivate --username admin
uv run mail-results-auth cleanup-sessions
```

Настройки перечислены в [.env.example](.env.example); рабочий `.env` не создаётся и не добавляется в Git.

## Гарантии

- `PUT /api/v1/internal/emails/{record_id}` принимает `payload`, `raw_email` и именованные `attachment_N` multipart parts.
- Одинаковые `record_id`, generation и payload возвращают idempotent `committed`; более старое generation и другой payload того же generation получают controlled `409`.
- Файлы проходят потоковую SHA-256/size-проверку, upload и `HEAD` до PostgreSQL transaction. При сбое БД загруженные, но не опубликованные объекты недоступны read API.
- `email_locator` сначала определяет receipt timestamp, после чего detail query обращается к одной monthly partition.
- Read-only API требует отдельный reader key, кроме явно включённого режима `ALLOW_ANONYMOUS_READER=true`.
  Также принимается действующая пользовательская Bearer-сессия.
  Все бинарные загрузки идут потоково через API, прямых MinIO URL нет.
- Список писем возвращает `id`, `subject`, `class_code` и `class_name_ru`; поля
  классификации всегда присутствуют и содержат строку либо `null`. Полная карточка
  письма возвращает тему, отправителя, время получения, нормализованное содержимое,
  общую сводку, классификацию, ключевые факты и скачиваемые вложения с отдельными
  сводками.
- `GET /api/v1/statistics` возвращает количество писем, вложений и распределение
  по классам за заданный временной интервал.

Подробнее: [архитектура](docs/architecture.md), [HTTP API](docs/api.md), [эксплуатация](docs/operations.md).
