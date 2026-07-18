# Эксплуатация и развёртывание

## Настройка окружения

Скопируйте `.env.example` в `.env` и задайте как минимум постоянный каталог моделей:

```dotenv
PADDLE_DEVICE=cpu
PADDLE_ENABLE_MKLDNN=false
PADDLE_MODEL_HOME=/models
MAX_CONCURRENT_INFERENCES=2
MODEL_CACHE_SIZE=4
```

`PADDLE_MODEL_HOME` должен быть доступен для записи. Сервис передаёт это значение в `PADDLE_PDX_CACHE_HOME`, используемый PaddleX для постоянного кэша загруженных моделей.

Для GPU установите совместимый GPU-wheel PaddlePaddle, задайте, например, `PADDLE_DEVICE=gpu:0`, и установите `MAX_CONCURRENT_INFERENCES=1`. CPU- и GPU-wheel PaddlePaddle нельзя устанавливать одновременно.

`PADDLE_ENABLE_MKLDNN=false` передаётся непосредственно в конвейеры PaddleOCR/PaddleX. Это важнее, чем переменная процесса `FLAGS_use_mkldnn`: PaddleX выбирает движок инференса при создании конвейера. Значение по умолчанию отключает oneDNN/MKL-DNN и предотвращает ошибку `ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]` на CPU. После изменения переменной перезапустите сервис: уже загруженные конвейеры остаются в LRU-кэше процесса.

Если необходима ускоренная обработка CPU, можно проверить `PADDLE_ENABLE_MKLDNN=true` на отдельном запросе. При повторении указанной ошибки верните `false`; для постоянной нагрузки предпочтителен GPU-режим.

## Локальный запуск

```bash
cd ocr-service
uv sync --extra dev --python 3.11
cp .env.example .env
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

После запуска доступны:

- `/docs` — Swagger UI;
- `/openapi.json` — спецификация OpenAPI;
- `/health/live` — liveness-probe;
- `/health/ready` — readiness-probe.

## Ubuntu 24.04: CPU-профиль

Для почтового агента на этом хосте OCR намеренно работает на CPU. Используйте
несекретный шаблон `cpu.env.example`; GPU-wheel PaddlePaddle не устанавливается:

```bash
cd ocr-service
uv sync --extra dev --python 3.11
cp cpu.env.example .env
uv run python -c 'import paddle; print(paddle.device.get_device())'
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Команда проверки должна вывести `cpu`. Первый запрос скачает официальные артефакты
PaddleOCR в `PADDLE_MODEL_HOME`, поэтому каталог должен сохраняться между
перезапусками и хосту нужен доступ к выбранному источнику моделей. Не заменяйте
CPU-wheel на GPU-wheel в этом environment.

В этом профиле OCR принимает запросы с другого хоста. API не использует ключ
доступа, поэтому на OCR-хосте разрешите TCP/8000 только адресу агента (замените
`AGENT_IP`):

```bash
sudo ufw allow from AGENT_IP to any port 8000 proto tcp
sudo ufw deny 8000/tcp
```

## Docker

```bash
cd ocr-service
docker build -t ocr-service .
docker run --rm -p 8000:8000 \
  -v paddle-models:/models \
  --env-file .env \
  ocr-service
```

Образ использует CPU и непривилегированного пользователя. Веса моделей не включаются в слои образа. Том `/models` переживает перезапуск контейнера, поэтому повторные запросы не загружают уже скачанные модели.

## Мониторинг

Используйте:

- `GET /health/live` для проверки доступности процесса;
- `GET /health/ready` для проверки конфигурации и каталогов;
- `loaded_models` в readiness-ответе для диагностики кэша;
- `X-Request-ID` для корреляции клиента с серверными логами.

Логи содержат идентификатор запроса, маршрут, статус, длительность, задачу, модель, язык, размер файла, количество страниц, время ожидания семафора, загрузки модели и инференса. Содержимое документов и OCR-результаты не логируются.

## Производительность и ресурсы

- Первый запрос к модели выполняет загрузку весов и обычно заметно медленнее последующих.
- `MODEL_CACHE_SIZE` выбирайте по доступной RAM/VRAM и числу реально используемых комбинаций моделей и языков.
- `MAX_CONCURRENT_INFERENCES` ограничивает суммарную нагрузку. Для CPU обычно подходит значение `1–2`; для GPU начните с `1`.
- `MAX_UPLOAD_SIZE_MB` и `MAX_PDF_PAGES` защищают сервис от чрезмерного потребления памяти и времени.
- При большом числе воркеров Uvicorn у каждого процесса будет свой кэш моделей; учитывайте это при планировании памяти.

## Обновление

1. Обновите исходный код и зависимости.
2. Выполните `uv lock --check`, `ruff format --check app tests`, `ruff check app tests` и `pytest`.
3. Разверните новый образ или перезапустите сервис.
4. Не удаляйте том моделей при обычном обновлении: это избавляет от повторной загрузки весов.

При обновлении PaddleOCR отдельно проверьте официальный API конвейеров и результат реального smoke-теста, поскольку адаптеры изолируют, но не отменяют возможные изменения сторонней библиотеки.
