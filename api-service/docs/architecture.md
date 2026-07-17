# Архитектура

```text
mail-agent -- multipart + writer key --> Results API
                                      ├─ PostgreSQL: locator, emails, attachments
                                      └─ MinIO: raw.eml и вложения
reader key --------------------------> Results API --> потоковый download
```

`email_locator` не partitioned и содержит `record_id`, `received_at`, generation и fingerprint payload. Таблицы `emails` и `email_attachments` declaratively partitioned по `received_at` месяцами. Detail lookup сначала читает locator, затем использует bounded predicate соответствующего месяца; list перебирает месяцы назад и не выполняет `OFFSET` или `COUNT(*)`.

Запись проходит: validation → streaming upload deterministic S3 keys → `HEAD` всех объектов → PostgreSQL transaction. Объекты без committed metadata не публикуются read API. Повторный PUT использует record id как idempotency key. Орphan cleanup удаляет только prefixes без locator и старше retention окна.

Имена partition строятся исключительно из внутреннего `datetime`; пользовательские данные никогда не становятся SQL identifiers или S3 paths.
