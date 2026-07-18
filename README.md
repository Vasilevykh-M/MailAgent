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

## Ubuntu 24.04: один хост с RTX 2060

На Linux-хосте с RTX 2060 запускаются Results API, LLM и worker. OCR уже работает
на отдельной CPU-машине по адресу `192.14.88.2:8000`. Compose публикует Results
API только на `127.0.0.1:8080`; PostgreSQL и MinIO не публикуются.

Сначала проверьте хост и подготовьте инфраструктуру. Рабочий `.env` содержит
секреты, поэтому создаётся только на сервере и не добавляется в Git:

```bash
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader
docker --version
docker compose version

cp .env.infrastructure.example .env
chmod 600 .env
# Заполните POSTGRES_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD,
# WRITER_API_KEY и READER_API_KEY в .env.
make infra-up
make health-data
```

OCR на CPU запускается на отдельной машине. Замена `paddlepaddle` на GPU-wheel не
требуется и не должна выполняться. На хосте агента достаточно проверить его
доступность:

```bash
curl --fail --silent --show-error --connect-timeout 3 \
  http://192.14.88.2:8000/health/ready
```

На OCR-хосте используйте [cpu.env.example](ocr-service/cpu.env.example) и
ограничьте TCP/8000 firewall только IP Linux-хоста с агентом.

Затем в третьей shell-сессии запустите LLM. Профиль использует
`Qwen/Qwen3.5-9B` в FP16, текстовый режим и CPU-offload; для карты с 8 ГиБ VRAM
нужны как минимум 32 ГиБ RAM. Сначала проверьте свободную память и GPU, затем
запустите сервис. Подробные ограничения и диагностика приведены в
[llm-service/README.md](llm-service/README.md).

```bash
cd llm-service
nvidia-smi --query-gpu=name,memory.total,memory.free,compute_cap,driver_version --format=csv,noheader
free -h
cp config.mk.example config.mk
make check-config
make install
make start
# В отдельной shell-сессии дождитесь готовности в make logs, затем:
make health
make smoke
```

После успешного `make health` подготовьте агент и запустите его на том же хосте.
Значение `RESULTS_API_KEY` должно совпадать с `WRITER_API_KEY` из инфраструктурного
файла; не записывайте его в `agent/config.yaml`.

```bash
cd ..
cp agent/config.example.yaml agent/config.yaml
cp yandex/mail/.env.example yandex/mail/.env
export LLM_BASE_URL=http://127.0.0.1:8001/v1
export LLM_API_KEY='set-from-secret-store-if-required'
export LLM_MODEL=qwen3.5-9b
export OCR_BASE_URL=http://192.14.88.2:8000
export RESULTS_API_BASE_URL=http://127.0.0.1:8080
export RESULTS_API_KEY='set-to-WRITER_API_KEY'
export OCR_FALLBACK_TO_VLM=false
uv sync --project agent --extra dev --python 3.11
uv run --project agent mail-agent doctor
uv run --project agent yandex-mail --env yandex/mail/.env auth
uv run --project agent mail-agent worker
```

Не подставляйте реальные секреты в repository-примеры и не открывайте `8001`,
`8080`, PostgreSQL или MinIO во внешний интернет. TCP/8000 OCR разрешайте только
между агентом и OCR-хостом. Для Docker Engine на Ubuntu 24.04, используемого
инфраструктурными контейнерами, применяйте
[официальную инструкцию Docker](https://docs.docker.com/engine/install/ubuntu/).

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
