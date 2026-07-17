"""Структурированное логирование без содержимого пользовательских данных."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TypeAlias

LogValue: TypeAlias = str | int | float | bool | None

# Форматтер намеренно пропускает только технические метаданные. Даже если
# сторонняя библиотека добавит к LogRecord текст письма или ответ LLM, в JSON
# он не попадёт.
SAFE_LOG_FIELDS = (
    "component",
    "service",
    "operation",
    "run_id",
    "record_id",
    "mailbox",
    "uid",
    "stage",
    "status",
    "failed_stage",
    "attempt",
    "max_attempts",
    "retryable",
    "duration_ms",
    "message_count",
    "processed_count",
    "attachment_count",
    "warning_count",
    "input_chars",
    "input_truncated",
    "output_chars",
    "input_bytes",
    "image_count",
    "model",
    "schema",
    "task",
    "ocr_model",
    "language",
    "http_method",
    "http_status",
    "error_type",
    "error_code",
    "validation_error_count",
    "finish_reason",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"timestamp": datetime.now(UTC).isoformat(), "level": record.levelname, "event": record.getMessage()}
        for name in SAFE_LOG_FIELDS:
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        return json.dumps(payload, ensure_ascii=False)


def log_event(logger: logging.Logger, event: str, *, level: int = logging.INFO, **fields: LogValue) -> None:
    """Пишет событие с проверенным белым списком технических полей."""

    unexpected = set(fields) - set(SAFE_LOG_FIELDS)
    if unexpected:
        raise ValueError(f"Небезопасные поля логирования: {', '.join(sorted(unexpected))}")
    logger.log(level, event, extra=fields)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # HTTP-клиент пишет URL каждой операции на INFO. Собственные события ниже
    # содержат попытку, статус и длительность без дублирования и query-параметров.
    logging.getLogger("httpx").setLevel(logging.WARNING)
