# Qwen3.5-9B через vLLM и Ray на Ubuntu 24.04 с RTX 5090

Сервис запускает `Qwen/Qwen3.5-9B` на одном хосте Ubuntu 24.04 с одной RTX 5090
по адресу `192.168.88.251`. Управление выполняется **только через Makefile**:
wrapper-скриптов и загрузки `.env` нет.

```text
mail-agent -> 192.168.88.251:8001/v1 -> vLLM -> Ray (локальный node) -> RTX 5090
```

API привязан к приватному адресу `192.168.88.251:8001`, поэтому mail-agent на
другом компьютере в доверенной LAN может обращаться к модели. Не открывайте порт
`8001` в интернет. Если сеть не полностью доверенная, передайте `VLLM_API_KEY`
через окружение и укажите его в настройках агента.

## Профиль RTX 5090

`Qwen3.5-9B` — мультимодальная модель. Агент передаёт в LLM только текст, поэтому
профиль включает `--language-model-only`: визуальные модули модели не загружаются,
а `OCR_FALLBACK_TO_VLM` у агента выключен.

Для RTX 5090 используется BF16 без выгрузки весов в оперативную память:

```make
DTYPE := bfloat16
MAX_MODEL_LEN := 8192
MAX_NUM_SEQS := 2
GPU_MEMORY_UTILIZATION := 0.90
CPU_OFFLOAD_GB := 0
LANGUAGE_MODEL_ONLY := true
```

32 ГиБ VRAM достаточно для модели и KV-cache без CPU-offload. Версия CUDA Toolkit
из `nvcc` не используется как источник wheel vLLM; фактическую совместимость
проверяет `make install` через PyTorch.

До установки убедитесь, что драйвер видит карту:

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free,compute_cap,driver_version --format=csv,noheader
```

Ошибка `No available memory for the cache blocks` означает, что после загрузки
весов не осталось места для KV-cache. Для неё сначала уменьшите в `config.mk`
`MAX_MODEL_LEN` до `4096`, затем `GPU_MEMORY_UTILIZATION` до `0.85`. Не
увеличивайте `MAX_NUM_SEQS`, пока сервис стабильно не проходит `make smoke`.

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

`config.mk` — несекретный файл. Шаблон уже настроен для `192.168.88.251`, одной
GPU `0` и одного локального Ray node. Если фактический адрес сервера отличается,
измените одновременно `HOST`, `BIND_HOST`, `RAY_HEAD_IP` и `RAY_NODE_IP`.
Не меняйте `PIPELINE_PARALLEL_SIZE`, `RAY_EXPECTED_NODES` или
`RAY_EXPECTED_GPUS` для этого профиля.

Репозиторий модели публичный, но при ограничениях Hugging Face можно передать
токен только через окружение:

```bash
export HF_TOKEN='...'
```

При необходимости защиты API перед первым запуском передайте ключ тем же способом:

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
нужен для данного запуска. Не копируйте его на единственный сервер с RTX 5090.

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
