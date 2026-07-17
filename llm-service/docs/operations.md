# Эксплуатация

## Установка

На обоих серверах из одинаковой версии проекта:

```bash
make install
```

## Конфигурация

Head использует `config.mk.example`, worker — `config.worker.mk.example`. Рабочее имя файла на каждом сервере — `config.mk`.

Makefile не читает `.env`. Секреты `VLLM_API_KEY` и `HF_TOKEN` передаются только через окружение процесса.

## Запуск

1. На head выполнить `make start`.
2. Пока head ждёт кластер, на worker выполнить `make start`.
3. На head читать `make logs`.
4. Проверить `make status`, `make cluster-status`, `make health` и `make smoke`.

## Остановка

На head:

```bash
make stop
```

Затем на worker:

```bash
make stop
```

## Диагностика

```bash
make status
make cluster-status
make logs
```

При зависании NCCL проверьте двустороннюю маршрутизацию, firewall и одинаковые значения:

```make
NCCL_SOCKET_IFNAME := wg0
GLOO_SOCKET_IFNAME := wg0
NCCL_IB_DISABLE := 1
NCCL_DEBUG := INFO
```

Для production верните `NCCL_DEBUG := WARN`.
