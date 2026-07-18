"""Доменные модели; бинарные данные не сериализуются в журналы или SQLite."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from .summarization.classification import EmailClassification

ToolName = Literal["programmatic", "vision", "ocr", "skip"]


class MessageReference(BaseModel):
    uid: str
    mailbox: str
    message_id: str | None = None
    date: datetime | None = None
    size_bytes: int = 0
    flags: list[str] = Field(default_factory=list)


class AttachmentMeta(BaseModel):
    original_filename: str
    safe_filename: str
    content_type: str
    detected_content_type: str
    extension: str
    size: int
    sha256: str
    is_inline: bool
    content_id: str | None = None
    file_path: str | None = None
    page_count: int | None = None
    has_text_layer: bool | None = None
    extracted_text_length: int = 0


class AttachmentPlan(BaseModel):
    tool: ToolName
    language: str | None = None
    ocr_task: str | None = None
    ocr_model: str | None = None
    output_format: str | None = None
    confidence: float = Field(ge=0, le=1)
    needs_visual_validation: bool = False
    reason: str = Field(min_length=1, max_length=600)
    validation_warnings: list[str] = Field(default_factory=list)


class AttachmentResult(AttachmentMeta):
    processing_tool: ToolName
    language: str | None = None
    raw_extracted_text: str | None = None
    corrected_text: str | None = None
    summary_ru: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    status: str = "processed"
    corrections: list[dict[str, str]] = Field(default_factory=list)


class FinalSummary(BaseModel):
    summary_ru: str
    classification: EmailClassification
    key_facts_ru: list[str] = Field(default_factory=list)
    action_items_ru: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    amounts: list[str] = Field(default_factory=list)
    document_numbers: list[str] = Field(default_factory=list)
    attachment_summaries: list[str] = Field(default_factory=list)
    warnings_ru: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class OCRCorrection(BaseModel):
    corrected_text: str
    corrections: list[dict[str, str]] = Field(default_factory=list)
    uncertain_fragments: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class AttachmentDigest(BaseModel):
    """Краткий результат анализа одного фрагмента или всего вложения."""

    summary_ru: str = Field(max_length=600)
    key_facts_ru: list[str] = Field(default_factory=list, max_length=4)
    action_items_ru: list[str] = Field(default_factory=list, max_length=4)
    deadlines: list[str] = Field(default_factory=list, max_length=4)
    warnings_ru: list[str] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0, le=1)


class MailProcessingState(TypedDict, total=False):
    run_id: str
    record_id: str
    pipeline_version: str
    processing_generation: int
    mailbox: str
    uid: str
    message_id: str | None
    message_metadata: dict[str, Any]
    normalized_body: str
    attachments: list[dict[str, Any]]
    # Пути и payload существуют только в текущем TemporaryDirectory; их нельзя переиспользовать после рестарта.
    attachment_payloads: list[dict[str, Any]]
    attachment_paths: dict[str, str]
    unavailable_attachment_names: list[str]
    attachment_plans: list[dict[str, Any]]
    attachment_results: list[dict[str, Any]]
    summary: dict[str, Any] | None
    api_record: dict[str, Any] | None
    api_commit_result: dict[str, Any] | None
    raw_email_path: str | None
    attempts: dict[str, int]
    warnings: list[str]
    errors: list[dict[str, str]]
    status: str
    failed_stage: str | None
    manual_review_stage: str | None
    manual_review_error_type: str | None
    temporary_dir: str
    pending_node_name: str | None
    pending_execution_key: str | None
