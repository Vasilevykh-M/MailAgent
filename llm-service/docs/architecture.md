# Архитектура

На каждом сервере работает локальный Ray node с одной RTX 5090. Head также запускает один процесс `vllm serve`, который подключается к существующему Ray-кластеру.

```text
client -> head:8001 -> vLLM driver -> Ray placement group
                                      |- head GPU: pipeline stage 0
                                      `- worker GPU: pipeline stage 1
```

Используется:

```text
tensor_parallel_size = 1
pipeline_parallel_size = 2
distributed_executor_backend = ray
```

Вся операционная логика находится в Makefile. `config.mk` содержит несекретные параметры узла. Worker не поднимает отдельный HTTP API.

Ray стартует из того же `.venv`, где установлен vLLM, поэтому удалённые Ray workers используют совместимое Python-окружение. `VLLM_HOST_IP` задаётся отдельно при запуске Ray на каждом узле.
