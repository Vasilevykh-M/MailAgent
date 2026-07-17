"""Normalized OCR result schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OcrLine(BaseModel):
    text: str
    confidence: float | None = None
    polygon: list[list[int | float]] | None = None


class OcrPage(BaseModel):
    page_index: int = Field(ge=0)
    width: int | None = None
    height: int | None = None
    text: str
    lines: list[OcrLine] = Field(default_factory=list)


class OcrResponse(BaseModel):
    request_id: str
    task: str = "ocr"
    model: str
    language: str
    page_count: int = Field(ge=1)
    text: str
    pages: list[OcrPage]
    processing_time_ms: int = Field(ge=0)
