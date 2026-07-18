# API

API — встроенный OpenAI-compatible сервер vLLM на локальном head:

```text
http://127.0.0.1:8001/v1
```

Проверки через Makefile:

```bash
make health
make models
make smoke
```

Пример:

```bash
curl http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.5-9b",
    "messages": [{"role": "user", "content": "Привет"}],
    "max_tokens": 256
  }'
```

При включённом `VLLM_API_KEY` добавьте `Authorization: Bearer ...`.

Профиль RTX 2060 запускает Qwen в режиме `--language-model-only`, поэтому API
принимает только текстовые сообщения. Изображения и удалённые мультимодальные
источники не поддерживаются; OCR выполняется отдельным CPU-сервисом.
