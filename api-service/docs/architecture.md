# Архитектура

```text
mail-agent -- multipart + writer key --> Results API
                                      ├─ PostgreSQL: locator, emails, attachments
                                      └─ MinIO: raw.eml и вложения
reader key / Bearer session ----------> Results API --> потоковый download
```

Compose размещает PostgreSQL и MinIO только в закрытой сети `data`. Results API
подключён к ней для доступа к хранилищам и к отдельной bridge-сети `api` для
publish-порта. По умолчанию порт привязан к `127.0.0.1`; внешняя привязка и
`ALLOW_ANONYMOUS_READER` включаются явно только для доверенной сети.

`email_locator` не partitioned и содержит `record_id`, `received_at`, generation и fingerprint payload. Таблицы `emails` и `email_attachments` declaratively partitioned по `received_at` месяцами. Detail lookup сначала читает locator, затем использует bounded predicate соответствующего месяца; list перебирает месяцы назад и не выполняет `OFFSET` или `COUNT(*)`.

Запись проходит: validation → streaming upload deterministic S3 keys → `HEAD` всех объектов → PostgreSQL transaction. Объекты без committed metadata не публикуются read API. Повторный PUT использует record id как idempotency key. Орphan cleanup удаляет только prefixes без locator и старше retention окна.

Имена partition строятся исключительно из внутреннего `datetime`; пользовательские данные никогда не становятся SQL identifiers или S3 paths.

Локальная аутентификация отделена от HTTP-router: `auth_users` содержит только
Argon2id hash, а `auth_sessions` — только SHA-256 digest криптографически
случайного opaque token. Login, bootstrap и CLI используют общий сервис и
транзакционный repository. На lifespan после доступности auth tables bootstrap
создаёт или синхронизирует администратора из `AUTH_ADMIN_*`; ошибка останавливает
запуск до readiness. При смене bootstrap-пароля сервис отзывает активные сессии.
Read dependencies сначала принимают совместимый технический reader key, затем
проверяют активную серверную сессию; writer dependency по-прежнему проверяет
только writer key. Пароли, tokens, их digests и auth headers не журналируются.
