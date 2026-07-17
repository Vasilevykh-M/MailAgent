# API

API — встроенный OpenAI-compatible сервер vLLM на head:

```text
http://192.14.88.2:8001/v1
```

Проверки через Makefile:

```bash
make health
make models
make smoke
```

Пример:

```bash
curl http://192.14.88.2:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.6-27b-fp8",
    "messages": [{"role": "user", "content": "Привет"}],
    "max_tokens": 256
  }'
```

При включённом `VLLM_API_KEY` добавьте `Authorization: Bearer ...`.

Мультимодальные HTTPS-источники по умолчанию запрещены фиктивным доменом `invalid.invalid`; Data URL остаются подходящим способом передавать локальные изображения. Для доверенного HTTPS-хоста замените `ALLOWED_MEDIA_DOMAIN` в `config.mk`.
