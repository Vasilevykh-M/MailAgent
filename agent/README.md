# Mail agent

`mail-agent` — worker Python 3.11+, который получает все непрочитанные письма Яндекс Почты, анализирует тело и вложения через OCR/LLM и сохраняет результат в независимый Results API. Яндекс Диск, Excel и Markdown-отчёты не участвуют в runtime.

## Поток

```text
unread pages → fetch(mark_read=False) → MIME во временный .eml
→ normalise / attachments / OCR / LLM → Results API multipart commit
→ result_committed → mark \Seen → completed
```

`record_id` зависит от mailbox, UID и Message-ID. Он служит ключом SQLite и HTTP idempotency key. `--reprocess` сохраняет тот же record ID и увеличивает `processing_generation`; API не разрешает старому generation перезаписать новое.

После API `committed` worker записывает SQLite status `result_committed` и минимальный checkpoint, затем ставит `\Seen`. Если процесс прерван между этими действиями, следующий запуск пропускает OCR/LLM и повторяет только установку флага. Старый SQLite status `table_committed` мигрируется в `discovered`: он не доказывает commit Results API.

## Классификация проекта

Итоговый анализ письма определяет одно основное направление и сохраняет его в
`agent_result.summary.classification`. Для решения используются тема, нормализованное
тело, все уровни пересылки, извлечённый текст и итоговые сводки вложений, а также
предупреждения о недоступных файлах. Содержимое письма и вложений остаётся
недоверенными данными и не может менять правила классификации.

Возможные коды: `3D_PRINTERS`, `CHEMISTRY`, `FOUNDRY`, `MOLD_PRINTING`,
`ROBOTIC_CELLS`, `PRODUCTION_LINES`, `MACHINES`, `TECHNICAL_VISION` и
`OTHER_EQUIPMENT`. Последний код используют только для явно промышленного
оборудования вне специализированных направлений, а не как запасной вариант для
неясного письма.

`classification.status` принимает одно из значений:

- `classified` — выбран ровно один код, русское название, причина и уверенность;
- `new_project` — ни одно направление семантически не подходит; `message_ru` всегда
  содержит точную фразу `Это новый проект`;
- `manual_review` — данных недостаточно из-за ошибки обработки, недоступного важного
  вложения или сбоя LLM. Это не является новым проектом.

Код, русское название, причина, уверенность и сообщение возвращаются только внутри
итоговой сводки; отдельное дублирование в payload не требуется.

## Конфигурация

```bash
cp agent/config.example.yaml agent/config.yaml
cp agent/.env.example .env
cp yandex/mail/.env.example yandex/mail/.env
```

В `config.yaml` задаётся `results_api.base_url`, timeout/retry/TLS. `RESULTS_API_KEY` передаётся только окружением. Пример:

```yaml
results_api:
  base_url: http://127.0.0.1:8080
  api_key: ""
  timeout_seconds: 300
  max_retries: 3
  verify_tls: true
```

## Запуск

```bash
make infra-up
export RESULTS_API_KEY='writer key from local secret store'
make install PROFILE=core
make auth-mail
make health PROFILE=core
make once
```

Команды ручного восстановления:

```bash
uv run --project agent mail-agent process --uid 123 --mailbox INBOX
uv run --project agent mail-agent process --uid 123 --mailbox INBOX --reprocess
uv run --project agent mail-agent retry-failed
uv run --project agent mail-agent dashboard
```

Панель на `127.0.0.1:8765` показывает `result_committed`, но не тело письма, бинарные данные или ключи. Полный contract и ограничения интеграций приведены в [docs/public-contracts.md](docs/public-contracts.md).
