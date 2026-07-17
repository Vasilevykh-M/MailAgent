"""Версионированные HTTP-схемы Results API."""

from __future__ import annotations

import base64
import json
import re
import unicodedata
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HeaderItem(APIModel):
    name: str = Field(min_length=1, max_length=998)
    value: str = Field(max_length=16_384)


class OriginalEmail(APIModel):
    subject: str = Field(default="", max_length=2_000)
    sender: str = Field(default="", alias="from", max_length=2_000)
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    reply_to: list[str] = Field(default_factory=list)
    headers: list[HeaderItem] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    size_bytes: int = Field(default=0, ge=0)
    text_plain: str = ""
    text_html: str = ""
    normalized_body: str = ""


class FileMetadata(APIModel):
    part_name: str = Field(pattern=r"^attachment_[0-9]+$")
    original_filename: str = Field(default="", max_length=1024)
    safe_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=255)
    detected_content_type: str = Field(default="application/octet-stream", max_length=255)
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    is_inline: bool = False
    content_id: str | None = Field(default=None, max_length=1024)

    @field_validator("safe_filename")
    @classmethod
    def no_path(cls, value: str) -> str:
        if "/" in value or "\\" in value or value in {".", ".."} or ".." in value:
            raise ValueError("safe_filename must not contain a path")
        normalized = unicodedata.normalize("NFKC", value)
        normalized = "".join(character for character in normalized if character.isprintable())
        sanitized = re.sub(r"[^\w.-]+", "_", normalized, flags=re.UNICODE).strip("._")
        if not sanitized:
            sanitized = "attachment"
        return sanitized[:255]


class IngestionPayload(APIModel):
    schema_version: int = Field(ge=1, le=1)
    record_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    pipeline_version: str = Field(min_length=1, max_length=64)
    processing_generation: int = Field(default=0, ge=0)
    mailbox: str = Field(min_length=1, max_length=512)
    uid: str = Field(min_length=1, max_length=512)
    message_id: str | None = Field(default=None, max_length=2048)
    received_at: datetime
    processed_at: datetime
    original_email: OriginalEmail
    agent_result: dict[str, Any]
    files: list[FileMetadata] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_parts(self) -> IngestionPayload:
        names = [item.part_name for item in self.files]
        if len(names) != len(set(names)):
            raise ValueError("files.part_name must be unique")
        return self

    def fingerprint(self) -> str:
        """Канонический payload для определения конфликта одного поколения."""

        from hashlib import sha256

        encoded = json.dumps(
            self.model_dump(mode="json", by_alias=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return sha256(encoded.encode("utf-8")).hexdigest()


class IngestionResponse(APIModel):
    record_id: str
    status: str = "committed"
    processing_generation: int
    attachment_count: int
    storage_verified: bool
    committed_at: datetime


class EmailListItem(APIModel):
    record_id: str
    received_at: datetime
    sender: str = Field(alias="from")
    subject: str
    summary_preview: str
    attachment_count: int
    confidence: float | None = None


class EmailListResponse(APIModel):
    items: list[EmailListItem]
    next_cursor: str | None = None
    has_more: bool


class AttachmentResponse(APIModel):
    attachment_id: str
    position: int
    original_filename: str
    safe_filename: str
    content_type: str
    detected_content_type: str
    size: int
    sha256: str
    is_inline: bool
    content_id: str | None
    processing_result: dict[str, Any] | None
    download_url: str


class EmailDetail(APIModel):
    record_id: str
    received_at: datetime
    processed_at: datetime
    mailbox: str
    uid: str
    message_id: str | None
    pipeline_version: str
    processing_generation: int
    original_email: OriginalEmail
    agent_result: dict[str, Any]
    attachments: list[AttachmentResponse]
    raw_download_url: str


def encode_cursor(received_at: datetime, record_id: str) -> str:
    value = json.dumps({"received_at": received_at.isoformat(), "record_id": record_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, str]:
    from .errors import ValidationAPIError

    try:
        padded = value + "=" * (-len(value) % 4)
        raw = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        timestamp, record = datetime.fromisoformat(str(raw["received_at"])), str(raw["record_id"])
        if not timestamp.tzinfo or len(record) != 64:
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationAPIError("Invalid cursor") from exc
    return timestamp, record
