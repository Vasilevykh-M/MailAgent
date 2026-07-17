"""Environment-backed application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings. No model is loaded while settings are constructed."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    paddle_device: str = "cpu"
    paddle_enable_mkldnn: bool = False
    paddle_model_home: Path = Path("./models")
    max_upload_size_mb: int = Field(default=25, ge=1, le=1024)
    max_pdf_pages: int = Field(default=50, ge=1, le=1000)
    max_concurrent_inferences: int = Field(default=2, ge=1, le=64)
    model_cache_size: int = Field(default=4, ge=1, le=32)
    default_ocr_model: str = "pp-ocrv6"
    default_ocr_language: str = "en"
    default_parser_model: str = "pp-structurev3"
    default_parser_language: str = "en"
    temp_dir: Path | None = None
    request_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    paddle_model_source: str = "huggingface"

    @field_validator("paddle_device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        allowed = ("cpu", "gpu", "npu", "xpu", "mlu", "dcu", "metax_gpu", "iluvatar_gpu")
        if not any(value == device or value.startswith(f"{device}:") for device in allowed):
            raise ValueError("PADDLE_DEVICE must be a supported Paddle device, such as cpu or gpu:0")
        return value

    @field_validator("paddle_model_source")
    @classmethod
    def validate_model_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"huggingface", "bos", "modelscope", "aistudio"}:
            raise ValueError("PADDLE_MODEL_SOURCE must be huggingface, bos, modelscope, or aistudio")
        return normalized

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def effective_temp_dir(self) -> Path:
        return self.temp_dir or self.paddle_model_home / "tmp"


def validate_runtime_directories(settings: Settings) -> None:
    """Verify writable persistent model and transient file locations without inference."""

    for directory in (settings.paddle_model_home, settings.effective_temp_dir):
        directory.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=directory, prefix="health-", delete=True):
            pass


@lru_cache
def get_settings() -> Settings:
    return Settings()
