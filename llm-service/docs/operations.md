# Эксплуатация

## Подготовка хоста

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free,compute_cap,driver_version --format=csv,noheader
free -h
sudo apt-get update
sudo apt-get install -y make curl ninja-build
```

Нужны одна доступная GPU `0`, не менее 32 ГиБ RAM и `uv` в `PATH`. Установленный
CUDA Toolkit не используется для выбора пакета vLLM; работоспособность CUDA
проверяется командой `make install`.

## Конфигурация и запуск

```bash
cd llm-service
cp config.mk.example config.mk
make check-config
make install
make start
```

`config.mk.example` задаёт API на `127.0.0.1`, а для Ray выбирает первый адрес из
`hostname -I`; при нескольких интерфейсах укажите один private/VPN IP вручную в
`RAY_HEAD_IP` и `RAY_NODE_IP`. Профиль использует одну GPU, FP16, контекст 4096,
один параллельный запрос, `GPU_MEMORY_UTILIZATION=0.90` и 14 ГиБ CPU-offload.
Веса модели сохраняются в `cache/huggingface`; не удаляйте этот каталог при
обычном перезапуске.

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
установите `GPU_MEMORY_UTILIZATION := 0.90`: этот параметр определяет доступный
KV-cache. При фактической CUDA OOM уменьшите сначала `MAX_MODEL_LEN` до `2048`,
затем `GPU_MEMORY_UTILIZATION` до `0.85`. Если ошибка указывает на RAM, освободите
или увеличьте память: уменьшение `CPU_OFFLOAD_GB` при 8 ГиБ VRAM не является
исправлением, потому что весам потребуется больше VRAM.

## Остановка

```bash
make stop
```
