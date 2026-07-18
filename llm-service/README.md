# Qwen3.5-9B через vLLM и Ray на одной RTX 2060

Сервис запускает `Qwen/Qwen3.5-9B` на одном Linux-хосте с одной видимой GPU.
Управление выполняется **только через Makefile**: wrapper-скриптов и загрузки
`.env` нет.

```text
mail-agent -> 127.0.0.1:8001/v1 -> vLLM -> Ray (локальный node) -> RTX 2060
```

API намеренно привязан к `127.0.0.1:8001`. Он доступен только процессам этого
хоста, включая mail-agent. Не открывайте vLLM напрямую в интернет; для удалённого
доступа нужен отдельный reverse proxy с TLS и аутентификацией.

## Ограничения профиля RTX 2060

`Qwen3.5-9B` — мультимодальная модель. Этот агент передаёт в LLM только текст,
поэтому профиль включает `--language-model-only`: визуальные модули модели не
загружаются, а `OCR_FALLBACK_TO_VLM` у агента выключен.

Для RTX 2060 используется FP16 и выгрузка части весов в оперативную память:

```make
DTYPE := half
MAX_MODEL_LEN := 4096
MAX_NUM_SEQS := 1
GPU_MEMORY_UTILIZATION := 0.90
CPU_OFFLOAD_GB := 14
LANGUAGE_MODEL_ONLY := true
```

Профиль рассчитан на карту с 8 ГиБ VRAM и **не менее 32 ГиБ RAM**. CPU-offload
позволяет загрузить модель, но делает ответы заметно медленнее из-за передачи
весов между RAM и GPU. Версия CUDA Toolkit из `nvcc` не используется как источник
wheel vLLM; фактическую совместимость проверяет `make install` через PyTorch.

До установки убедитесь, что драйвер видит карту и достаточно доступной RAM:

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free,compute_cap,driver_version --format=csv,noheader
free -h
```

Если свободной RAM меньше 24 ГиБ или `make start` завершается ошибкой памяти, не
запускайте mail-agent: сначала освободите/увеличьте RAM. Ошибка `No available
memory for the cache blocks` означает, что после загрузки весов не осталось места
для KV-cache: на выделенной GPU установите `GPU_MEMORY_UTILIZATION := 0.90`.
Для фактической CUDA OOM уменьшите в `config.mk` `MAX_MODEL_LEN` до `2048`, затем
`GPU_MEMORY_UTILIZATION` до `0.85`; не увеличивайте параллелизм.

## Установка и настройка

На Ubuntu 24.04 нужны `make`, `curl`, `ninja-build`, доступный в `PATH` `uv`,
драйвер NVIDIA и интернет для первого скачивания Python, пакетов и модели.
Локальная Python из Ubuntu не обязана быть 3.13: `uv` загрузит её в управляемое
окружение при `make install`.

```bash
sudo apt-get update
sudo apt-get install -y make curl ninja-build

cd llm-service
cp config.mk.example config.mk
make check-config
make install
```

`config.mk` — несекретный файл. Шаблон уже настроен для одного хоста и одной GPU
`0`; API остаётся на loopback, а для Ray автоматически выбирается первый адрес из
`hostname -I`. Если на сервере несколько интерфейсов, укажите один private/VPN IP
в `RAY_HEAD_IP` и `RAY_NODE_IP`. Не меняйте `PIPELINE_PARALLEL_SIZE`,
`RAY_EXPECTED_NODES` или `RAY_EXPECTED_GPUS` для этого профиля.

Репозиторий модели публичный, но при ограничениях Hugging Face можно передать
токен только через окружение:

```bash
export HF_TOKEN='...'
```

При необходимости защиты локального API перед первым запуском передайте ключ тем
же способом:

```bash
export VLLM_API_KEY='...'
```

Не сохраняйте эти значения в `config.mk` или в Git.

## Запуск и проверка

```bash
cd llm-service
make start
make logs
```

Первый запуск скачивает веса в `cache/huggingface` и затем загружает модель. После
строки о готовности API в логе выполните в другой shell-сессии:

```bash
cd llm-service
make health
make models
make smoke
```

Ожидаемый идентификатор модели в `/v1/models` — `qwen3.5-9b`. Для запуска в
foreground вместо `make start` используйте `make run`.

Статус GPU, локального Ray и HTTP API:

```bash
make status
make cluster-status
```

Нормальный вывод `make cluster-status` содержит один живой узел и `GPU=1.0`.

## Остановка

```bash
cd llm-service
make stop
```

Команда останавливает только vLLM с проверенным PID и Ray, отмеченный этим
Makefile. Она не затрагивает другие процессы GPU.

## Дополнительный worker

`config.worker.mk.example` сохранён для отдельной двухузловой конфигурации и не
нужен для данного запуска. Не копируйте его на единственный сервер с RTX 2060.

## Основные команды

```bash
make help
make check-config
make install
make start
make run
make status
make cluster-status
make health
make models
make smoke
make logs
make stop
```
