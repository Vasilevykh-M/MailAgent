"""Строго валидируемая YAML/env-конфигурация агента."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, PositiveInt, field_validator

from .exceptions import ConfigurationError


class _Model(BaseModel):
    model_config = {"extra": "forbid"}


class MailSettings(_Model):
    mailbox: str = "INBOX"
    poll_interval_seconds: PositiveInt = 60
    unread_only: bool = True
    batch_size: PositiveInt = 50
    max_concurrent_messages: PositiveInt = 1
    mark_read_after_success: bool = True
    max_message_size: PositiveInt = 25 * 1024 * 1024


class LLMSettings(_Model):
    base_url: str = "http://192.168.88.251:8001/v1"
    api_key: str = ""
    model: str = ""
    timeout_seconds: PositiveInt = 180
    max_retries: int = Field(default=3, ge=0, le=10)
    final_summary_attempts: int = Field(default=3, ge=1, le=5)
    max_concurrent_requests: PositiveInt = 1
    max_images_per_request: PositiveInt = 2
    # Консервативный лимит для Qwen с контекстом 8k: включает текст письма и вложений.
    max_text_chars_per_request: PositiveInt = 8_000
    max_completion_tokens: PositiveInt = 1_200
    # Коррекция OCR возвращает исходный текст целиком и поэтому требует большего бюджета.
    max_ocr_correction_tokens: PositiveInt = 3_000
    max_image_bytes_per_request: PositiveInt = 4 * 1024 * 1024
    circuit_breaker_failures: PositiveInt = 3


class OCRSettings(_Model):
    base_url: str = "http://127.0.0.1:8000"
    timeout_seconds: PositiveInt = 300
    max_retries: int = Field(default=3, ge=0, le=10)
    max_concurrent_requests: PositiveInt = 1
    capabilities_cache_ttl_seconds: PositiveInt = 300
    fallback_to_vlm: bool = True


class ResultsAPISettings(_Model):
    """Несекретные настройки контрактного API; ключ передаётся только через окружение."""

    base_url: str = "http://127.0.0.1:8080"
    api_key: str = ""
    timeout_seconds: PositiveInt = 300
    max_retries: int = Field(default=3, ge=0, le=10)
    verify_tls: bool = True


class TableSettings(_Model):
    """Устаревшая модель для изолированных legacy-утилит; AgentSettings её не использует."""

    remote_path: str = "/mail-agent/mail-register.xlsx"
    sheet_name: str = "Письма"
    header_row: PositiveInt = 1
    create_if_missing: bool = False
    update_existing: bool = True
    max_conflict_retries: int = Field(default=3, ge=0, le=10)
    save_full_report: bool = True
    report_directory: str = "/mail-agent/reports"
    columns: dict[str, str] = Field(
        default_factory=lambda: {
            "sender": "Отправитель",
            "message_date": "Дата письма",
            "subject": "Тема",
            "summary": "Итоговая суммаризация",
            "attachment_summary": "Суммаризация вложений",
            "key_facts": "Ключевые факты и особенности",
            "record_id": "ID записи",
        }
    )


class LimitsSettings(_Model):
    max_attachment_size: PositiveInt = 25 * 1024 * 1024
    max_attachments_per_message: PositiveInt = 30
    max_pdf_pages: PositiveInt = 50
    max_pptx_slides: PositiveInt = 100
    max_xlsx_sheets: PositiveInt = 20
    max_xlsx_rows: PositiveInt = 10_000
    max_xlsx_columns: PositiveInt = 100
    max_parallel_attachments: PositiveInt = 1
    chunk_size: PositiveInt = 4_000
    max_attachment_summary_chunks: PositiveInt = 24
    message_body_chunk_size: PositiveInt = 3_000
    max_message_body_summary_chunks: PositiveInt = 24


class RetrySettings(_Model):
    max_attempts: PositiveInt = 5
    base_backoff_seconds: PositiveInt = 15
    max_backoff_seconds: PositiveInt = 900
    permanent_error_retry: bool = False


class DashboardSettings(_Model):
    """Read-only панель наблюдения за агентом на loopback или trusted LAN."""

    host: str = "127.0.0.1"
    port: PositiveInt = 8765
    queue_limit: PositiveInt = 100
    recent_limit: PositiveInt = 30

    @field_validator("host")
    @classmethod
    def trusted_dashboard_host(cls, value: str) -> str:
        if value == "localhost":
            return value
        try:
            address = ip_address(value)
        except ValueError as exc:
            raise ValueError("Dashboard host must be localhost or an IP address.") from exc
        if address.is_unspecified or not (address.is_loopback or address.is_private):
            raise ValueError("Dashboard host must be a loopback or private/VPN address.")
        return value


class AgentSettings(_Model):
    work_dir: Path = Path("./var/mail-agent")
    db_path: Path = Path("./var/mail-agent/state.sqlite3")
    checkpoint_db_path: Path = Path("./var/mail-agent/checkpoints.sqlite3")
    mail_env_file: Path = Path("./yandex/mail/.env")
    log_level: str = "INFO"
    pipeline_version: str = "3"
    mail: MailSettings = Field(default_factory=MailSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    ocr: OCRSettings = Field(default_factory=OCRSettings)
    results_api: ResultsAPISettings = Field(default_factory=ResultsAPISettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)
    retries: RetrySettings = Field(default_factory=RetrySettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)

    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        value = value.upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")
        return value

    def prepare_directories(self) -> None:
        try:
            self.work_dir.mkdir(parents=True, exist_ok=True)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigurationError("Не удалось подготовить рабочий каталог агента.") from exc


_ENV: dict[str, tuple[str, ...]] = {
    "AGENT_WORK_DIR": ("work_dir",),
    "AGENT_DB_PATH": ("db_path",),
    "AGENT_CHECKPOINT_DB_PATH": ("checkpoint_db_path",),
    "MAIL_ENV_FILE": ("mail_env_file",),
    "LOG_LEVEL": ("log_level",),
    "PIPELINE_VERSION": ("pipeline_version",),
    "MAILBOX": ("mail", "mailbox"),
    "POLL_INTERVAL_SECONDS": ("mail", "poll_interval_seconds"),
    "MAIL_BATCH_SIZE": ("mail", "batch_size"),
    "MAX_CONCURRENT_MESSAGES": ("mail", "max_concurrent_messages"),
    "MARK_READ_AFTER_SUCCESS": ("mail", "mark_read_after_success"),
    "LLM_BASE_URL": ("llm", "base_url"),
    "LLM_API_KEY": ("llm", "api_key"),
    "LLM_MODEL": ("llm", "model"),
    "LLM_TIMEOUT_SECONDS": ("llm", "timeout_seconds"),
    "LLM_MAX_RETRIES": ("llm", "max_retries"),
    "LLM_FINAL_SUMMARY_ATTEMPTS": ("llm", "final_summary_attempts"),
    "LLM_MAX_TEXT_CHARS_PER_REQUEST": ("llm", "max_text_chars_per_request"),
    "LLM_MAX_COMPLETION_TOKENS": ("llm", "max_completion_tokens"),
    "LLM_MAX_OCR_CORRECTION_TOKENS": ("llm", "max_ocr_correction_tokens"),
    "LLM_MAX_IMAGE_BYTES_PER_REQUEST": ("llm", "max_image_bytes_per_request"),
    "MESSAGE_BODY_CHUNK_SIZE": ("limits", "message_body_chunk_size"),
    "MAX_MESSAGE_BODY_SUMMARY_CHUNKS": ("limits", "max_message_body_summary_chunks"),
    "OCR_BASE_URL": ("ocr", "base_url"),
    "OCR_TIMEOUT_SECONDS": ("ocr", "timeout_seconds"),
    "OCR_MAX_RETRIES": ("ocr", "max_retries"),
    "OCR_FALLBACK_TO_VLM": ("ocr", "fallback_to_vlm"),
    "RESULTS_API_BASE_URL": ("results_api", "base_url"),
    "RESULTS_API_KEY": ("results_api", "api_key"),
    "RESULTS_API_TIMEOUT_SECONDS": ("results_api", "timeout_seconds"),
    "RESULTS_API_MAX_RETRIES": ("results_api", "max_retries"),
    "RESULTS_API_VERIFY_TLS": ("results_api", "verify_tls"),
    "DASHBOARD_HOST": ("dashboard", "host"),
    "DASHBOARD_PORT": ("dashboard", "port"),
}

_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _read_environment_file(path: Path) -> dict[str, str]:
    """Читает простой dotenv-файл без shell-подстановок и выполнения кода."""

    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError("Не удалось прочитать файл окружения агента.") from exc

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not _ENVIRONMENT_NAME.fullmatch(key):
            raise ConfigurationError(f"Некорректная строка {line_number} в файле окружения агента.")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _results_api_base_url(environment: Mapping[str, str]) -> str:
    """Строит URL Results API из тех же host/port, что использует Compose."""

    host = environment.get("RESULTS_API_HOST", "").strip()
    if not host:
        return ""
    port = environment.get("RESULTS_API_PORT", "8080").strip() or "8080"
    rendered_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"http://{rendered_host}:{port}"


def _set_path(target: dict[str, Any], path: tuple[str, ...], value: str) -> None:
    cursor = target
    for key in path[:-1]:
        child = cursor.get(key)
        if not isinstance(child, dict):
            child = {}
            cursor[key] = child
        cursor = child
    cursor[path[-1]] = value


def load_settings(config_file: str | Path | None = None, environ: Mapping[str, str] | None = None) -> AgentSettings:
    """Загружает YAML, корневой `.env` и затем переменные процесса.

    Файл `.env` читается как данные, без выполнения shell-кода. Он единый для
    Docker Compose и worker: `WRITER_API_KEY` становится ключом Results API.
    """

    process_env = os.environ if environ is None else environ
    config_path = Path(config_file or process_env.get("AGENT_CONFIG", "./agent/config.yaml"))
    environment_file = Path(process_env.get("AGENT_ENV_FILE", ".env"))
    env = _read_environment_file(environment_file)
    env.update(process_env)
    if not env.get("RESULTS_API_KEY") and env.get("WRITER_API_KEY"):
        env["RESULTS_API_KEY"] = env["WRITER_API_KEY"]
    if not process_env.get("RESULTS_API_BASE_URL"):
        results_api_base_url = _results_api_base_url(env)
        if results_api_base_url:
            env["RESULTS_API_BASE_URL"] = results_api_base_url
    data: dict[str, Any] = {}
    if config_path.exists():
        try:
            parsed = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError("Не удалось безопасно прочитать YAML-конфигурацию.") from exc
        if not isinstance(parsed, dict):
            raise ConfigurationError("Корень YAML-конфигурации должен быть объектом.")
        data = parsed
    results_api_value = data.get("results_api")
    if isinstance(results_api_value, dict) and results_api_value.get("api_key"):
        raise ConfigurationError("results_api.api_key должен передаваться только через окружение.")
    for name, path in _ENV.items():
        if name in env and env[name] != "":
            _set_path(data, path, env[name])
    try:
        return AgentSettings.model_validate(data)
    except Exception as exc:
        raise ConfigurationError("Конфигурация агента не прошла проверку.") from exc
