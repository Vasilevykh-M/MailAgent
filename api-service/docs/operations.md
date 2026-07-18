# Эксплуатация

## Миграции и партиции

`make api-migrate` применяет Alembic. Initial migration создаёт default, previous/current и три future partitions; `mail-results-partitions` поддерживает horizon из `PARTITIONS_MONTHS_AHEAD`. Запускайте его ежедневным maintenance job, а не из HTTP-request.

## Backup и восстановление

Делайте согласованные регулярные `pg_dump` PostgreSQL и versioned/replicated backup MinIO bucket. При восстановлении сначала поднимите PostgreSQL и MinIO volumes, примените migrations, затем проверьте `/health/ready`. Не публикуйте API, пока не восстановлены оба хранилища.

## Ключи и TLS

Writer и reader keys различны. Ротируйте их через secret manager/reverse proxy: добавьте новый key, перезапустите API и worker, затем удалите прежний. `ALLOW_ANONYMOUS_READER=true` отключает reader key только для read-only API, включая выдачу тел писем и вложений; используйте его только для теста в доверенной сети и ограничьте доступ firewall. Write API остаётся защищён writer key. В production размещайте API только за TLS-terminating reverse proxy, ограничивайте request body, закрывайте PostgreSQL/MinIO в private network и не доверяйте входящему `X-Forwarded-*` без настройки proxy.

## Orphan cleanup и обновление

После сбоя PostgreSQL uploaded S3 objects остаются закрытыми. Удаляйте только старые, не связанные с locator prefixes:

```bash
docker compose exec api-service .venv/bin/mail-results-orphans --older-than-hours 72
```

Перед обновлением сделайте backup volumes, примените новую миграцию отдельной командой, затем rolling restart `api-service`. Persistent volumes `postgres-data` и `minio-data` не удаляются командой `make infra-down`.

Ограничения: list запрос ограничен 100 записями и 120 месяцами поиска; загрузки ограничены настроенными message/attachment limits.
