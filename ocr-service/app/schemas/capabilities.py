"""Capability discovery response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelCapabilityResponse(BaseModel):
    id: str
    name: str
    languages: list[str]
    description: str
    supports_pdf: bool = True
    supports_images: bool = True
    output_formats: list[str] | None = None


class TaskCapabilityResponse(BaseModel):
    models: list[ModelCapabilityResponse]
    default_model: str
    default_language: str
    supported_mime_types: list[str]
    supported_extensions: list[str]
    max_upload_size_mb: int
    max_pdf_pages: int
    lazy_model_loading: bool = True


class CapabilitiesResponse(BaseModel):
    tasks: dict[str, TaskCapabilityResponse]
    output_formats: list[str] = Field(default_factory=lambda: ["json", "markdown", "both"])
