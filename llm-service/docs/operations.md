# Эксплуатация

## Подготовка хоста

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free,compute_cap,driver_version --format=csv,noheader
free -h
sudo apt-get update
sudo apt-get install -y make curl ninja-build
```

Нужны одна доступная RTX 5090 как GPU `0` и `uv` в `PATH`. Установленный CUDA
Toolkit не используется для выбора пакета vLLM; работоспособность CUDA проверяется
командой `make install`.

## Конфигурация и запуск

```bash
cd llm-service
cp config.mk.example config.mk
make check-config
make install
make start
```

`config.mk.example` задаёт API и Ray на `192.168.88.251`; при изменении адреса
синхронно поменяйте `HOST`, `BIND_HOST`, `RAY_HEAD_IP` и `RAY_NODE_IP`. Профиль
использует одну GPU, BF16, контекст 8192, до двух одновременных последовательностей,
`GPU_MEMORY_UTILIZATION=0.90` и без CPU-offload. Веса модели сохраняются в
`cache/huggingface`; не удаляйте этот каталог при обычном перезапуске.

При необходимости передайте секреты только текущему процессу:

```bash
export HF_TOKEN='...'
export VLLM_API_KEY='...'
make start
```

## Проверка и диагностика

```bash
make logs
make health
make models
make smoke
make status
make cluster-status
```

При ошибке `No available memory for the cache blocks` остановите сервис и
уменьшите сначала `MAX_MODEL_LEN` до `4096`, затем
`GPU_MEMORY_UTILIZATION` до `0.85`. `GPU_MEMORY_UTILIZATION` определяет объём
памяти для весов, активаций и KV-cache. Не включайте CPU-offload для этого профиля:
он замедляет инференс и не требуется 32 ГиБ VRAM RTX 5090.

## Остановка

```bash
make stop
```
