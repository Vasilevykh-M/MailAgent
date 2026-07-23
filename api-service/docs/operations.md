# Эксплуатация

## Миграции и партиции

`make api-migrate` применяет Alembic. Initial migration создаёт default, previous/current и три future partitions; `mail-results-partitions` поддерживает horizon из `PARTITIONS_MONTHS_AHEAD`. Запускайте его ежедневным maintenance job, а не из HTTP-request.

## Администратор и сессии

После применения migrations можно задать bootstrap-пользователя только двумя
переменными одновременно:

```bash
export AUTH_ADMIN_USERNAME=admin
export AUTH_ADMIN_PASSWORD='replace-with-a-strong-secret'
uv run uvicorn app.main:app
```

В контейнерной среде передавайте их через secret manager, например:

```yaml
environment:
  AUTH_ADMIN_USERNAME: ${AUTH_ADMIN_USERNAME}
  AUTH_ADMIN_PASSWORD: ${AUTH_ADMIN_PASSWORD}
```

Отсутствие обеих переменных отключает bootstrap, не удаляя пользователей. Одна
заданная переменная — ошибка запуска. При смене `AUTH_ADMIN_PASSWORD` и рестарте
пароль обновляется, а сессии пользователя отзываются. Не храните пароль в Git,
compose-файлах или логах: в PostgreSQL остаётся только Argon2id hash.

`AUTH_SESSION_TTL_SECONDS` по умолчанию равен `28800` (8 часов),
`AUTH_TOKEN_BYTES` по умолчанию равен `32` и не может быть меньше `32`.
Старые сессии очищайте отдельной scheduled job, а не фоновым циклом web-процесса:

```bash
uv run mail-results-auth cleanup-sessions
```

Команда удаляет истёкшие и давно отозванные записи по `DATABASE_URL`, печатает
только их число. Retention отозванных сессий по умолчанию 7 дней и задаётся
`AUTH_REVOKED_SESSION_RETENTION_SECONDS`. Для ручного создания, смены пароля и
deactivation используйте `mail-results-users`; пароль CLI читает через TTY.

## Backup и восстановление

Делайте согласованные регулярные `pg_dump` PostgreSQL и versioned/replicated backup MinIO bucket. При восстановлении сначала поднимите PostgreSQL и MinIO volumes, примените migrations, затем проверьте `/health/ready`. Не публикуйте API, пока не восстановлены оба хранилища.

## Ключи и TLS

Writer и reader keys различны. Ротируйте их через secret manager/reverse proxy: добавьте новый key, перезапустите API и worker, затем удалите прежний. Read-only API также принимает пользовательскую Bearer-сессию. `ALLOW_ANONYMOUS_READER=true` отключает reader/session check только для read-only API, включая выдачу тел писем и вложений; используйте его только для теста в доверенной сети и ограничьте доступ firewall. Write API остаётся защищён только writer key. В production размещайте API только за TLS-terminating reverse proxy, ограничивайте request body, закрывайте PostgreSQL/MinIO в private network и не доверяйте входящему `X-Forwarded-*` без настройки proxy.

## Orphan cleanup и обновление

После сбоя PostgreSQL uploaded S3 objects остаются закрытыми. Удаляйте только старые, не связанные с locator prefixes:

```bash
docker compose exec api-service .venv/bin/mail-results-orphans --older-than-hours 72
```

Перед обновлением сделайте backup volumes, примените новую миграцию отдельной командой, затем rolling restart `api-service`. Persistent volumes `postgres-data` и `minio-data` не удаляются командой `make infra-down`.

Ограничения: list запрос ограничен 100 записями и 120 месяцами поиска; загрузки ограничены настроенными message/attachment limits.
