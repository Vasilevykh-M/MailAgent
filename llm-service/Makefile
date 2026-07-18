# Прямое управление Ray-кластером и встроенным OpenAI-compatible сервером vLLM.
# Makefile не читает .env и не использует wrapper-скрипты. Несекретные параметры
# задаются в config.mk; VLLM_API_KEY и HF_TOKEN передаются через окружение.

SHELL := /bin/bash
.SHELLFLAGS := -Eeuo pipefail -c
.ONESHELL:
.NOTPARALLEL:

-include config.mk

UV ?= uv
VENV ?= .venv
PYTHON := $(VENV)/bin/python
VLLM := $(VENV)/bin/vllm
RAY := $(VENV)/bin/ray

LOG_DIR := logs
RUN_DIR := run
LOG_FILE := $(LOG_DIR)/vllm.log
PID_FILE := $(RUN_DIR)/vllm.pid
RAY_MARKER_FILE := $(RUN_DIR)/ray-node.marker

NODE_ROLE ?= head
MODEL ?= Qwen/Qwen3.5-9B
SERVED_MODEL_NAME ?= qwen3.5-9b
HOST ?= 192.168.88.251
BIND_HOST ?= 192.168.88.251
PORT ?= 8001
CUDA_VISIBLE_DEVICES ?= 0
HF_HOME ?= $(CURDIR)/cache/huggingface

RAY_HEAD_IP ?= 192.168.88.251
RAY_NODE_IP ?= 192.168.88.251
RAY_PORT ?= 6379
RAY_EXPECTED_NODES ?= 1
RAY_EXPECTED_GPUS ?= 1
RAY_CLUSTER_START_TIMEOUT ?= 900
RAY_NODE_MANAGER_PORT ?= 10002
RAY_OBJECT_MANAGER_PORT ?= 10003
RAY_MIN_WORKER_PORT ?= 11000
RAY_MAX_WORKER_PORT ?= 11100
RAY_DASHBOARD_AGENT_PORT ?= 52365
RAY_DASHBOARD_AGENT_GRPC_PORT ?= 52366
RAY_RUNTIME_ENV_AGENT_PORT ?= 52367
RAY_ADDRESS := $(RAY_HEAD_IP):$(RAY_PORT)

TENSOR_PARALLEL_SIZE ?= 1
PIPELINE_PARALLEL_SIZE ?= 1
DISTRIBUTED_EXECUTOR_BACKEND ?= ray
MAX_MODEL_LEN ?= 8192
MAX_NUM_SEQS ?= 2
GPU_MEMORY_UTILIZATION ?= 0.90
CPU_OFFLOAD_GB ?= 0
DTYPE ?= bfloat16
KV_CACHE_DTYPE ?= auto
ENABLE_PREFIX_CACHING ?= false
CALCULATE_KV_SCALES ?= false
LANGUAGE_MODEL_ONLY ?= true
REASONING_PARSER ?=
ENABLE_AUTO_TOOL_CHOICE ?= false
TOOL_CALL_PARSER ?=

NCCL_SOCKET_IFNAME ?=
GLOO_SOCKET_IFNAME ?=
NCCL_DEBUG ?= WARN
NCCL_IB_DISABLE ?=

VLLM_BASE_ARGS = serve "$(MODEL)" \
	--host "$(BIND_HOST)" \
	--port "$(PORT)" \
	--served-model-name "$(SERVED_MODEL_NAME)" \
	--tensor-parallel-size "$(TENSOR_PARALLEL_SIZE)" \
	--pipeline-parallel-size "$(PIPELINE_PARALLEL_SIZE)" \
	--distributed-executor-backend "$(DISTRIBUTED_EXECUTOR_BACKEND)" \
	--max-model-len "$(MAX_MODEL_LEN)" \
	--max-num-seqs "$(MAX_NUM_SEQS)" \
	--gpu-memory-utilization "$(GPU_MEMORY_UTILIZATION)" \
	--cpu-offload-gb "$(CPU_OFFLOAD_GB)" \
	--dtype "$(DTYPE)" \
	--kv-cache-dtype "$(KV_CACHE_DTYPE)"

ifeq ($(ENABLE_PREFIX_CACHING),true)
VLLM_BASE_ARGS += --enable-prefix-caching
endif
ifeq ($(CALCULATE_KV_SCALES),true)
VLLM_BASE_ARGS += --calculate-kv-scales
endif
ifeq ($(LANGUAGE_MODEL_ONLY),true)
VLLM_BASE_ARGS += --language-model-only
endif
ifneq ($(strip $(REASONING_PARSER)),)
VLLM_BASE_ARGS += --reasoning-parser "$(REASONING_PARSER)"
endif
ifeq ($(ENABLE_AUTO_TOOL_CHOICE),true)
VLLM_BASE_ARGS += --enable-auto-tool-choice --tool-call-parser "$(TOOL_CALL_PARSER)"
endif

.DEFAULT_GOAL := help
.PHONY: help install check-config check-cli ray-start ray-stop wait-cluster \
	run start stop stop-api status cluster-status health models logs smoke check

help:
	@printf '%s\n' \
	  'Стартовый профиль: Ubuntu 24.04, одна RTX 5090, Qwen3.5-9B.' \
	  '' \
	  'make install          создать .venv и установить зависимости из uv.lock' \
	  'make start            head: Ray + vLLM в фоне' \
	  'make run              head: Ray + vLLM в foreground' \
	  'make stop             остановить локальные процессы сервиса и локальный Ray' \
	  'make status           проверить локальный узел, Ray-кластер и API' \
	  'make cluster-status   показать Ray-узлы и их GPU-ресурсы' \
	  'make health | models  проверить vLLM API на HOST:PORT' \
	  'make smoke            выполнить короткий chat-completion запрос' \
	  'make logs             читать logs/vllm.log на head' \
	  '' \
	  'Параметры: config.mk. Секреты: VLLM_API_KEY/HF_TOKEN только в окружении.'

install:
	@command -v "$(UV)" >/dev/null || { echo 'uv is required.' >&2; exit 1; }
	@command -v nvidia-smi >/dev/null || { echo 'nvidia-smi is required.' >&2; exit 1; }
	@command -v ninja >/dev/null || { echo 'Install ninja-build first: sudo apt-get install -y ninja-build' >&2; exit 1; }
	@"$(UV)" venv --python 3.13 --seed "$(VENV)"
	@"$(UV)" sync --frozen
	@env CUDA_VISIBLE_DEVICES="$(CUDA_VISIBLE_DEVICES)" "$(PYTHON)" -c 'import ray,torch,vllm; assert torch.cuda.is_available(), "CUDA unavailable"; assert torch.cuda.device_count()==1, f"expected one visible GPU, got {torch.cuda.device_count()}"; print("vLLM",vllm.__version__,"Ray",ray.__version__,"CUDA",torch.version.cuda,"GPU",torch.cuda.get_device_name(0))'
	@"$(VLLM)" serve --help >/dev/null
	@"$(RAY)" start --help >/dev/null

check-config:
	@test "$(NODE_ROLE)" = head || test "$(NODE_ROLE)" = worker || { echo 'NODE_ROLE must be head or worker.' >&2; exit 1; }
	@test "$(MODEL)" = 'Qwen/Qwen3.5-9B' || { echo 'MODEL must be Qwen/Qwen3.5-9B.' >&2; exit 1; }
	@test -n "$(SERVED_MODEL_NAME)" && test -n "$(HOST)" && test -n "$(BIND_HOST)"
	@test "$(PORT)" -gt 0 && test "$(PORT)" -le 65535
	@test "$(RAY_PORT)" -gt 0 && test "$(RAY_PORT)" -le 65535
	@test "$(RAY_EXPECTED_NODES)" -ge 1 && test "$(RAY_EXPECTED_GPUS)" -ge 1
	@test "$(CUDA_VISIBLE_DEVICES)" = 0 || { echo 'Each server must expose exactly GPU 0.' >&2; exit 1; }
	@test "$(TENSOR_PARALLEL_SIZE)" -eq 1 || { echo 'TENSOR_PARALLEL_SIZE must be 1 for one GPU per server.' >&2; exit 1; }
	@test "$(PIPELINE_PARALLEL_SIZE)" -ge 1
	@test "$(DISTRIBUTED_EXECUTOR_BACKEND)" = ray
	@test $$(( $(TENSOR_PARALLEL_SIZE) * $(PIPELINE_PARALLEL_SIZE) )) -eq "$(RAY_EXPECTED_GPUS)"
	@test "$(MAX_MODEL_LEN)" -gt 0 && test "$(MAX_NUM_SEQS)" -gt 0
	@test "$(CPU_OFFLOAD_GB)" -ge 0
	@[[ "$(DTYPE)" = half || "$(DTYPE)" = bfloat16 ]] || { echo 'DTYPE must be half or bfloat16.' >&2; exit 1; }
	@test "$(LANGUAGE_MODEL_ONLY)" = true || { echo 'LANGUAGE_MODEL_ONLY must be true for this text-only profile.' >&2; exit 1; }
	@awk 'BEGIN { value=$(GPU_MEMORY_UTILIZATION); exit !(value >= 0.50 && value < 1.0) }' || { echo 'GPU_MEMORY_UTILIZATION must be in [0.50, 1.0).' >&2; exit 1; }
	@if [[ "$(NODE_ROLE)" = head && "$(RAY_NODE_IP)" != "$(RAY_HEAD_IP)" ]]; then echo 'On head, RAY_NODE_IP must equal RAY_HEAD_IP.' >&2; exit 1; fi
	@if [[ "$(NODE_ROLE)" = worker && "$(RAY_NODE_IP)" = "$(RAY_HEAD_IP)" ]]; then echo 'Worker RAY_NODE_IP must differ from RAY_HEAD_IP.' >&2; exit 1; fi
	@if [[ "$(NODE_ROLE)" = worker && "$(RAY_EXPECTED_NODES)" -lt 2 ]]; then echo 'Worker requires at least two Ray nodes.' >&2; exit 1; fi

check-cli: check-config
	@test -x "$(PYTHON)" && test -x "$(VLLM)" && test -x "$(RAY)" || { echo 'Run make install first.' >&2; exit 1; }
	@if ! vllm_help="$$("$(VLLM)" serve --help=all 2>&1)"; then vllm_help="$$("$(VLLM)" serve --help 2>&1)"; fi; \
	flags=(--host --port --served-model-name --tensor-parallel-size --pipeline-parallel-size --distributed-executor-backend --max-model-len --max-num-seqs --gpu-memory-utilization --cpu-offload-gb --dtype --kv-cache-dtype); \
	[[ "$(ENABLE_PREFIX_CACHING)" != true ]] || flags+=(--enable-prefix-caching); \
	[[ "$(CALCULATE_KV_SCALES)" != true ]] || flags+=(--calculate-kv-scales); \
	[[ "$(LANGUAGE_MODEL_ONLY)" != true ]] || flags+=(--language-model-only); \
	[[ -z "$(REASONING_PARSER)" ]] || flags+=(--reasoning-parser); \
	[[ "$(ENABLE_AUTO_TOOL_CHOICE)" != true ]] || flags+=(--enable-auto-tool-choice --tool-call-parser); \
	[[ -z "$${VLLM_API_KEY:-}" ]] || flags+=(--api-key); \
	for flag in "$${flags[@]}"; do grep -q -- "$$flag" <<<"$$vllm_help" || { echo "Installed vLLM lacks $$flag" >&2; exit 1; }; done
	@ray_start_help="$$("$(RAY)" start --help 2>&1)"; \
	for flag in --node-ip-address --object-manager-port --node-manager-port --min-worker-port --max-worker-port --num-gpus --dashboard-agent-listen-port --dashboard-agent-grpc-port --runtime-env-agent-port --disable-usage-stats --head --port --include-dashboard --address; do \
	  grep -q -- "$$flag" <<<"$$ray_start_help" || { echo "Installed Ray lacks $$flag" >&2; exit 1; }; \
	done; \
	"$(RAY)" stop --help 2>&1 | grep -q -- '--grace-period' || { echo 'Installed Ray lacks --grace-period.' >&2; exit 1; }

ray-start: check-cli
	@mkdir -p "$(LOG_DIR)" "$(RUN_DIR)" "$(HF_HOME)"
	@if [[ -f "$(RAY_MARKER_FILE)" ]] && "$(PYTHON)" -c 'import ray,sys; ray.init(address=sys.argv[1],logging_level="ERROR",log_to_driver=False); ok=any(n.get("Alive") and n.get("NodeManagerAddress")==sys.argv[2] for n in ray.nodes()); ray.shutdown(); raise SystemExit(0 if ok else 1)' "$(RAY_ADDRESS)" "$(RAY_NODE_IP)" >/dev/null 2>&1; then \
	  echo "Ray $(NODE_ROLE) is already connected at $(RAY_NODE_IP)."; \
	  exit 0; \
	fi
	@rm -f "$(RAY_MARKER_FILE)"
	@if [[ "$(NODE_ROLE)" = worker ]]; then \
	  echo "Waiting for Ray head at $(RAY_ADDRESS)..."; \
	  reachable=false; \
	  for _ in $$(seq 1 "$(RAY_CLUSTER_START_TIMEOUT)"); do \
	    if "$(PYTHON)" -c 'import socket,sys; s=socket.socket(); s.settimeout(1); raise SystemExit(0 if s.connect_ex((sys.argv[1],int(sys.argv[2])))==0 else 1)' "$(RAY_HEAD_IP)" "$(RAY_PORT)"; then reachable=true; break; fi; \
	    sleep 1; \
	  done; \
	  [[ "$$reachable" = true ]] || { echo 'Ray head is unreachable.' >&2; exit 1; }; \
	fi
	@env_args=(CUDA_VISIBLE_DEVICES="$(CUDA_VISIBLE_DEVICES)" HF_HOME="$(HF_HOME)" VLLM_HOST_IP="$(RAY_NODE_IP)" TOKENIZERS_PARALLELISM=false NCCL_DEBUG="$(NCCL_DEBUG)"); \
	if [[ -n "$(NCCL_SOCKET_IFNAME)" ]]; then env_args+=(NCCL_SOCKET_IFNAME="$(NCCL_SOCKET_IFNAME)"); fi; \
	if [[ -n "$(GLOO_SOCKET_IFNAME)" ]]; then env_args+=(GLOO_SOCKET_IFNAME="$(GLOO_SOCKET_IFNAME)"); fi; \
	if [[ -n "$(NCCL_IB_DISABLE)" ]]; then env_args+=(NCCL_IB_DISABLE="$(NCCL_IB_DISABLE)"); fi; \
	args=(start --node-ip-address "$(RAY_NODE_IP)" --object-manager-port "$(RAY_OBJECT_MANAGER_PORT)" --node-manager-port "$(RAY_NODE_MANAGER_PORT)" --min-worker-port "$(RAY_MIN_WORKER_PORT)" --max-worker-port "$(RAY_MAX_WORKER_PORT)" --dashboard-agent-listen-port "$(RAY_DASHBOARD_AGENT_PORT)" --dashboard-agent-grpc-port "$(RAY_DASHBOARD_AGENT_GRPC_PORT)" --runtime-env-agent-port "$(RAY_RUNTIME_ENV_AGENT_PORT)" --num-gpus 1 --disable-usage-stats); \
	if [[ "$(NODE_ROLE)" = head ]]; then args+=(--head --port "$(RAY_PORT)" --include-dashboard=false); else args+=(--address "$(RAY_ADDRESS)"); fi; \
	echo "Starting Ray $(NODE_ROLE) at $(RAY_NODE_IP)..."; \
	env "$${env_args[@]}" "$(RAY)" "$${args[@]}"; \
	printf 'role=%s\nhead=%s\nnode=%s\nport=%s\n' "$(NODE_ROLE)" "$(RAY_HEAD_IP)" "$(RAY_NODE_IP)" "$(RAY_PORT)" >"$(RAY_MARKER_FILE)"
	@for _ in $$(seq 1 "$(RAY_CLUSTER_START_TIMEOUT)"); do \
	  if "$(PYTHON)" -c 'import ray,sys; ray.init(address=sys.argv[1],logging_level="ERROR",log_to_driver=False); ok=any(n.get("Alive") and n.get("NodeManagerAddress")==sys.argv[2] for n in ray.nodes()); ray.shutdown(); raise SystemExit(0 if ok else 1)' "$(RAY_ADDRESS)" "$(RAY_NODE_IP)" >/dev/null 2>&1; then \
	    echo "Ray node $(RAY_NODE_IP) is connected."; exit 0; \
	  fi; sleep 1; \
	done; echo 'Ray node did not become visible.' >&2; rm -f "$(RAY_MARKER_FILE)"; exit 1

wait-cluster: check-cli
	@test "$(NODE_ROLE)" = head || { echo 'wait-cluster is head-only.' >&2; exit 1; }
	@echo "Waiting for $(RAY_EXPECTED_NODES) Ray nodes and $(RAY_EXPECTED_GPUS) GPUs..."
	@for _ in $$(seq 1 "$(RAY_CLUSTER_START_TIMEOUT)"); do \
	  counts="$$("$(PYTHON)" -c 'import ray,sys; ray.init(address=sys.argv[1],logging_level="ERROR",log_to_driver=False); nodes=[n for n in ray.nodes() if n.get("Alive")]; print(len(nodes),int(sum(float(n.get("Resources",{}).get("GPU",0)) for n in nodes))); ray.shutdown()' "$(RAY_ADDRESS)" 2>/dev/null || echo '0 0')"; \
	  read -r nodes gpus <<<"$$counts"; \
	  if [[ "$$nodes" -eq "$(RAY_EXPECTED_NODES)" && "$$gpus" -eq "$(RAY_EXPECTED_GPUS)" ]]; then echo "Ray cluster ready: nodes=$$nodes GPUs=$$gpus"; exit 0; fi; \
	  sleep 1; \
	done; echo 'Timed out waiting for the complete Ray cluster.' >&2; exit 1

run: check-cli ray-start
	@test "$(NODE_ROLE)" = head || { echo 'make run is head-only; use make start on worker.' >&2; exit 1; }
	@$(MAKE) --no-print-directory wait-cluster
	@mkdir -p "$(LOG_DIR)" "$(RUN_DIR)" "$(HF_HOME)"
	@api_args=(); [[ -z "$${VLLM_API_KEY:-}" ]] || api_args+=(--api-key "$${VLLM_API_KEY}"); \
	env_args=(CUDA_VISIBLE_DEVICES="$(CUDA_VISIBLE_DEVICES)" HF_HOME="$(HF_HOME)" RAY_ADDRESS="$(RAY_ADDRESS)" VLLM_HOST_IP="$(RAY_NODE_IP)" TOKENIZERS_PARALLELISM=false NCCL_DEBUG="$(NCCL_DEBUG)"); \
	[[ -z "$${HF_TOKEN:-}" ]] || env_args+=(HF_TOKEN="$${HF_TOKEN}"); \
	[[ -z "$(NCCL_SOCKET_IFNAME)" ]] || env_args+=(NCCL_SOCKET_IFNAME="$(NCCL_SOCKET_IFNAME)"); \
	[[ -z "$(GLOO_SOCKET_IFNAME)" ]] || env_args+=(GLOO_SOCKET_IFNAME="$(GLOO_SOCKET_IFNAME)"); \
	[[ -z "$(NCCL_IB_DISABLE)" ]] || env_args+=(NCCL_IB_DISABLE="$(NCCL_IB_DISABLE)"); \
	echo "Starting vLLM foreground at http://$(HOST):$(PORT)/v1"; \
	exec env "$${env_args[@]}" "$(VLLM)" $(VLLM_BASE_ARGS) "$${api_args[@]}"

start: check-cli ray-start
	@if [[ "$(NODE_ROLE)" = worker ]]; then \
	  echo 'Worker joined Ray and contributes one GPU. vLLM API runs only on head.'; \
	  "$(MAKE)" --no-print-directory cluster-status || true; \
	  exit 0; \
	fi
	@$(MAKE) --no-print-directory wait-cluster
	@mkdir -p "$(LOG_DIR)" "$(RUN_DIR)" "$(HF_HOME)"
	@if [[ -f "$(PID_FILE)" ]] && kill -0 "$$(<"$(PID_FILE)")" 2>/dev/null; then echo 'vLLM is already running.' >&2; exit 1; fi
	@rm -f "$(PID_FILE)"
	@api_args=(); [[ -z "$${VLLM_API_KEY:-}" ]] || api_args+=(--api-key "$${VLLM_API_KEY}"); \
	env_args=(CUDA_VISIBLE_DEVICES="$(CUDA_VISIBLE_DEVICES)" HF_HOME="$(HF_HOME)" RAY_ADDRESS="$(RAY_ADDRESS)" VLLM_HOST_IP="$(RAY_NODE_IP)" TOKENIZERS_PARALLELISM=false NCCL_DEBUG="$(NCCL_DEBUG)"); \
	[[ -z "$${HF_TOKEN:-}" ]] || env_args+=(HF_TOKEN="$${HF_TOKEN}"); \
	[[ -z "$(NCCL_SOCKET_IFNAME)" ]] || env_args+=(NCCL_SOCKET_IFNAME="$(NCCL_SOCKET_IFNAME)"); \
	[[ -z "$(GLOO_SOCKET_IFNAME)" ]] || env_args+=(GLOO_SOCKET_IFNAME="$(GLOO_SOCKET_IFNAME)"); \
	[[ -z "$(NCCL_IB_DISABLE)" ]] || env_args+=(NCCL_IB_DISABLE="$(NCCL_IB_DISABLE)"); \
	nohup env "$${env_args[@]}" "$(VLLM)" $(VLLM_BASE_ARGS) "$${api_args[@]}" >"$(LOG_FILE)" 2>&1 & echo $$! >"$(PID_FILE)"; \
	echo "Started vLLM PID $$(<"$(PID_FILE)"). Follow: make logs"

stop-api:
	@if [[ ! -f "$(PID_FILE)" ]]; then echo 'vLLM PID file is absent.'; exit 0; fi; \
	pid="$$(<"$(PID_FILE)")"; command="$$(ps -p "$$pid" -o command= 2>/dev/null || true)"; \
	if ! kill -0 "$$pid" 2>/dev/null; then rm -f "$(PID_FILE)"; echo 'vLLM process is already stopped.'; exit 0; fi; \
	if [[ "$$command" != *"$(VLLM)"* || "$$command" != *'serve'* ]]; then echo 'Refusing to stop an unverified PID.' >&2; exit 1; fi; \
	kill -TERM "$$pid"; \
	for _ in $$(seq 1 30); do kill -0 "$$pid" 2>/dev/null || break; sleep 1; done; \
	kill -0 "$$pid" 2>/dev/null && kill -KILL "$$pid" || true; \
	rm -f "$(PID_FILE)"; echo "Stopped vLLM PID $$pid."

ray-stop:
	@if [[ ! -f "$(RAY_MARKER_FILE)" ]]; then echo 'Managed Ray marker is absent; local Ray was not stopped.'; exit 0; fi
	@echo "Stopping managed local Ray $(NODE_ROLE)..."
	@"$(RAY)" stop --grace-period 30 || true
	@rm -f "$(RAY_MARKER_FILE)"

stop: stop-api ray-stop

cluster-status: check-cli
	@"$(PYTHON)" -c 'import ray,sys; ray.init(address=sys.argv[1],logging_level="ERROR",log_to_driver=False); nodes=sorted((n for n in ray.nodes() if n.get("Alive")),key=lambda n:n.get("NodeManagerAddress","")); print("Ray address:",sys.argv[1]); print("Alive nodes:",len(nodes)); [print("- {}: GPU={}, CPU={}".format(n.get("NodeManagerAddress","?"),n.get("Resources",{}).get("GPU",0),n.get("Resources",{}).get("CPU",0))) for n in nodes]; ray.shutdown()' "$(RAY_ADDRESS)"

status: check-config
	@echo "Role: $(NODE_ROLE); node IP: $(RAY_NODE_IP); Ray head: $(RAY_ADDRESS)"
	@nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free,driver_version --format=csv,noheader -i "$(CUDA_VISIBLE_DEVICES)" || true
	@if [[ -x "$(PYTHON)" ]]; then "$(MAKE)" --no-print-directory cluster-status || true; fi
	@if [[ "$(NODE_ROLE)" = head ]]; then \
	  if [[ -f "$(PID_FILE)" ]] && kill -0 "$$(<"$(PID_FILE)")" 2>/dev/null; then echo "vLLM PID $$(<"$(PID_FILE)") is running."; else echo 'vLLM PID is not running.'; fi; \
	  "$(MAKE)" --no-print-directory health || true; \
	fi

health:
	@curl --fail --silent --show-error --connect-timeout 3 --max-time 10 "http://$(HOST):$(PORT)/health" >/dev/null
	@echo "vLLM health is ready at http://$(HOST):$(PORT)/health"

models:
	@auth=(); [[ -z "$${VLLM_API_KEY:-}" ]] || auth=(-H "Authorization: Bearer $${VLLM_API_KEY}"); \
	curl --fail --silent --show-error --connect-timeout 3 --max-time 15 "$${auth[@]}" "http://$(HOST):$(PORT)/v1/models"

logs:
	@tail -n 120 -f "$(LOG_FILE)"

smoke: health
	@auth=(); [[ -z "$${VLLM_API_KEY:-}" ]] || auth=(-H "Authorization: Bearer $${VLLM_API_KEY}"); \
	curl --fail --silent --show-error "$${auth[@]}" "http://$(HOST):$(PORT)/v1/chat/completions" \
	  -H 'Content-Type: application/json' \
	  -d '{"model":"$(SERVED_MODEL_NAME)","messages":[{"role":"user","content":"Ответь одним словом: готов"}],"max_tokens":16}'

check:
	@$(MAKE) --no-print-directory check-config
	@grep -q '^# Makefile не читает .env' Makefile
	@! grep -RInE '(scripts/(start|run|stop|status)\.sh|source[[:space:]]+.*\.env)' README.md docs AGENTS.md Makefile
