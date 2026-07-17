"""Normalized document parsing result schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentElement(BaseModel):
    id: str
    type: str
    text: str | None = None
    confidence: float | None = None
    bbox: list[int | float] | None = None
    polygon: list[list[int | float]] | None = None
    reading_order: int | None = None
    html: str | None = None
    table: Any | None = None
    markdown: str | None = None
    formula: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentPage(BaseModel):
    page_index: int = Field(ge=0)
    width: int | None = None
    height: int | None = None
    elements: list[DocumentElement] = Field(default_factory=list)


class DocumentParseResponse(BaseModel):
    request_id: str
    task: str = "document_parsing"
    model: str
    language: str
    page_count: int = Field(ge=1)
    pages: list[DocumentPage]
    markdown: str | None = None
    processing_time_ms: int = Field(ge=0)
