AGENT_DIR ?= ./agent
MAIL_DIR ?= ./yandex/mail
DRIVE_DIR ?= ./yandex/drive
LLM_DIR ?= ./llm-service
OCR_DIR ?= ./ocr-service
PROFILE ?= core
UV_CACHE_DIR ?= /private/tmp/mail-agent-uv-cache

.DEFAULT_GOAL := help
.PHONY: help install auth-mail auth-drive health health-core health-ai run once worker dashboard process retry-failed start stop status test lint typecheck check clean

help:
	@printf '%s\n' 'make install PROFILE=core|ai|all' 'make auth-mail | auth-drive' 'make health PROFILE=core|ai|all' 'make run PROFILE=core|ai|all' 'make once | worker | dashboard | process UID=123 MAILBOX=INBOX | retry-failed' 'make start|stop|status PROFILE=ai' 'make test | lint | typecheck | check | clean'

install:
	@test -d "$(AGENT_DIR)" && test -d "$(MAIL_DIR)" && test -d "$(DRIVE_DIR)"
	@echo "Installing profile $(PROFILE)"
	@if [ "$(PROFILE)" = core ] || [ "$(PROFILE)" = all ]; then UV_CACHE_DIR="$(UV_CACHE_DIR)" uv sync --project "$(AGENT_DIR)" --extra dev --python 3.11; fi
	@if [ "$(PROFILE)" = ai ] || [ "$(PROFILE)" = all ]; then test -d "$(LLM_DIR)" && test -d "$(OCR_DIR)"; UV_CACHE_DIR="$(UV_CACHE_DIR)" uv sync --project "$(OCR_DIR)" --extra dev --python 3.11; fi
	@if [ "$(PROFILE)" != core ] && [ "$(PROFILE)" != ai ] && [ "$(PROFILE)" != all ]; then echo 'PROFILE must be core, ai or all' >&2; exit 2; fi

auth-mail:
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" yandex-mail --env "$(MAIL_DIR)/.env" auth

auth-drive:
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" yandex-drive --env "$(DRIVE_DIR)/.env" auth

health: health-$(PROFILE)
health-core:
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" mail-agent doctor
health-ai:
	@curl --fail --silent --show-error http://127.0.0.1:8001/health >/dev/null
	@curl --fail --silent --show-error http://127.0.0.1:8000/health/ready >/dev/null
health-all: health-core health-ai

run:
	@echo "Running profile $(PROFILE)"
	@if [ "$(PROFILE)" = core ]; then $(MAKE) worker; elif [ "$(PROFILE)" = ai ]; then $(MAKE) start PROFILE=ai; else $(MAKE) start PROFILE=ai && $(MAKE) worker; fi

once:
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" mail-agent once
worker:
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" mail-agent worker
dashboard:
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" mail-agent dashboard
process:
	@test -n "$(UID)"
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" mail-agent process --uid "$(UID)" --mailbox "$(or $(MAILBOX),INBOX)"
retry-failed:
	@UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run --project "$(AGENT_DIR)" mail-agent retry-failed $(if $(INCLUDE_PERMANENT),--include-permanent)

start:
	@test "$(PROFILE)" = ai || test "$(PROFILE)" = all
	@cd "$(LLM_DIR)" && ./scripts/start.sh
	@"$(AGENT_DIR)/scripts/ocr-service.sh" start "$(OCR_DIR)"
stop:
	@test "$(PROFILE)" = ai || test "$(PROFILE)" = all
	@"$(AGENT_DIR)/scripts/ocr-service.sh" stop "$(OCR_DIR)"
	@cd "$(LLM_DIR)" && ./scripts/stop.sh
status:
	@test "$(PROFILE)" = ai || test "$(PROFILE)" = all
	@cd "$(LLM_DIR)" && ./scripts/status.sh
	@"$(AGENT_DIR)/scripts/ocr-service.sh" status "$(OCR_DIR)"

test:
	@cd "$(AGENT_DIR)" && UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run pytest
lint:
	@cd "$(AGENT_DIR)" && UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run ruff format --check src tests
	@cd "$(AGENT_DIR)" && UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run ruff check src tests
typecheck:
	@cd "$(AGENT_DIR)" && UV_CACHE_DIR="$(UV_CACHE_DIR)" uv run mypy src/mail_agent
check: lint typecheck test
clean:
	@rm -rf "$(AGENT_DIR)/.venv" "$(AGENT_DIR)/.pytest_cache" "$(AGENT_DIR)/.ruff_cache" "$(AGENT_DIR)/.mypy_cache" "$(AGENT_DIR)/var"
