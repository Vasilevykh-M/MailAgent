# Qwen3.6-27B-FP8 через vLLM и Ray на двух серверах

Сервис запускает `Qwen/Qwen3.6-27B-FP8` на двух Linux-серверах, по одной RTX 5090 32 ГБ на каждом. Управление выполняется **только через Makefile**. Wrapper-скриптов и загрузки `.env` нет.

```text
head:   RTX 5090 + Ray head + vLLM API :8001 + pipeline stage 0
worker: RTX 5090 + Ray worker            + pipeline stage 1

TP=1 × PP=2 = 2 GPU
```

API доступен клиентам по адресу:

```text
http://192.14.88.2:8001/v1
```

## 1. Требования

На обоих серверах:

- Linux x86_64;
- одна RTX 5090, доступная как GPU `0`;
- одинаковая копия сервиса и одинаковый `uv.lock`;
- `uv`, `nvidia-smi`, `ninja`;
- двусторонняя связь между приватными/VPN IP серверов.

Ray, NCCL и PyTorch distributed не следует пускать через открытый интернет. Наиболее надёжный вариант — WireGuard или приватная сеть с разрешённым трафиком между двумя адресами целиком.

## 2. Установка на обоих серверах

```bash
cd llm-service
make install
```

Команда создаёт `.venv`, устанавливает зафиксированные vLLM/Ray-зависимости и проверяет одну видимую CUDA GPU.

## 3. Конфигурация head

В архиве `config.mk` уже подготовлен как конфигурация head:

```make
NODE_ROLE := head
HOST := 192.14.88.2
BIND_HOST := 0.0.0.0
PORT := 8001

RAY_HEAD_IP := 192.14.88.2
RAY_NODE_IP := 192.14.88.2
```

`HOST` — адрес API для клиентов. `RAY_HEAD_IP` и `RAY_NODE_IP` должны быть IP сетевого интерфейса head, который напрямую доступен worker.

Когда `192.14.88.2` является публичным NAT-адресом, не используйте его как `RAY_NODE_IP`. Оставьте:

```make
HOST := 192.14.88.2
```

а для Ray укажите приватный/VPN IP head, например:

```make
RAY_HEAD_IP := 10.10.0.11
RAY_NODE_IP := 10.10.0.11
NCCL_SOCKET_IFNAME := wg0
GLOO_SOCKET_IFNAME := wg0
NCCL_IB_DISABLE := 1
```

## 4. Конфигурация worker

На втором сервере:

```bash
cp config.worker.mk.example config.mk
nano config.mk
```

Обязательно задайте реальные адреса:

```make
NODE_ROLE := worker
RAY_HEAD_IP := 10.10.0.11
RAY_NODE_IP := 10.10.0.12

NCCL_SOCKET_IFNAME := wg0
GLOO_SOCKET_IFNAME := wg0
NCCL_IB_DISABLE := 1
```

Все модельные параметры на head и worker должны совпадать.

## 5. Запуск

Откройте две SSH-сессии.

Сначала на head:

```bash
make start
```

Head запустит локальный Ray и будет ждать два узла и две GPU.

Затем на worker:

```bash
make start
```

Worker подключит свою RTX 5090 к Ray. После этого команда на head продолжит выполнение и запустит vLLM в фоне.

Лог на head:

```bash
make logs
```

Foreground-режим vLLM на head:

```bash
make run
```

На worker для подключения используется `make start`, а не `make run`.

## 6. Проверка

На любом сервере:

```bash
make status
make cluster-status
```

Ожидается:

```text
Alive nodes: 2
GPU=1.0 на каждом узле
```

На head или API-клиенте:

```bash
make health
make models
make smoke
```

Либо напрямую:

```bash
curl http://192.14.88.2:8001/health
curl http://192.14.88.2:8001/v1/models
```

## 7. Остановка

Сначала на head остановите API и локальный Ray:

```bash
make stop
```

Затем на worker:

```bash
make stop
```

Команда использует PID-файл только для vLLM этого сервиса и marker-файл только для локального Ray, запущенного Makefile.

## 8. Сетевые порты

Makefile фиксирует основные Ray-порты:

```text
6379
10002-10003
11000-11100
52365-52367
```

Однако NCCL/PyTorch могут создавать дополнительные межузловые TCP-соединения. Поэтому для VPN/приватной сети лучше разрешить весь TCP-трафик **только между IP head и worker**, а наружу открыть лишь `8001/tcp` для доверенных API-клиентов.

## 9. Параметры модели

Стартовый профиль:

```make
MODEL := Qwen/Qwen3.6-27B-FP8
TENSOR_PARALLEL_SIZE := 1
PIPELINE_PARALLEL_SIZE := 2
DISTRIBUTED_EXECUTOR_BACKEND := ray
MAX_MODEL_LEN := 8192
MAX_NUM_SEQS := 1
GPU_MEMORY_UTILIZATION := 0.90
```

При OOM сначала уменьшайте `MAX_MODEL_LEN`, затем `MAX_IMAGES_PER_PROMPT`. Не выставляйте `GPU_MEMORY_UTILIZATION := 1.0`.

## 10. Секреты

Не записывайте ключи в `config.mk`. Передавайте их через окружение:

```bash
export VLLM_API_KEY='...'
export HF_TOKEN='...'
make start
```

При API-ключе используйте то же окружение для `make models` и `make smoke`.

## Основные команды

```bash
make help
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
