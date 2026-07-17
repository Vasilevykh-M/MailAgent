"""Строгая конфигурация Results API из окружения."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field, PositiveInt, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Секреты не сериализуются и не должны попадать в журналы."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql+asyncpg://mail_agent:mail_agent@127.0.0.1:5432/mail_agent"
    s3_endpoint_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:9000")
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_bucket: str = "mail-agent"
    s3_region: str = "us-east-1"
    s3_secure: bool = False
    writer_api_key: SecretStr = SecretStr("")
    reader_api_key: SecretStr = SecretStr("")
    max_message_bytes: PositiveInt = 25 * 1024 * 1024
    max_attachment_bytes: PositiveInt = 25 * 1024 * 1024
    max_attachments_per_message: PositiveInt = 30
    partitions_months_ahead: int = Field(default=3, ge=0, le=24)
    log_level: str = "INFO"

    @field_validator("s3_bucket")
    @classmethod
    def valid_bucket(cls, value: str) -> str:
        if not 3 <= len(value) <= 63 or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for character in value
        ):
            raise ValueError("S3_BUCKET must be a valid DNS-compatible bucket name")
        return value

    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        value = value.upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
