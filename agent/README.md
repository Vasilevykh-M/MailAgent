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
