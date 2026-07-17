"""One validated source of truth for models, languages and task compatibility."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import (
    IncompatibleModelLanguageError,
    IncompatibleModelTaskError,
    UnsupportedLanguageError,
    UnsupportedModelError,
    UnsupportedOutputFormatError,
)
from app.schemas.capabilities import CapabilitiesResponse, ModelCapabilityResponse, TaskCapabilityResponse

OCR_TASK = "ocr"
DOCUMENT_TASK = "document_parsing"
SUPPORTED_MIME_TYPES = ("image/jpeg", "image/png", "application/pdf")
SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".pdf")


@dataclass(frozen=True)
class ModelCapability:
    id: str
    name: str
    languages: tuple[str, ...]
    description: str
    output_formats: tuple[str, ...] | None = None


class CapabilitiesRegistry:
    """Validates requests before any PaddleOCR pipeline is constructed."""

    def __init__(self) -> None:
        self._tasks: dict[str, tuple[ModelCapability, ...]] = {
            OCR_TASK: (
                ModelCapability(
                    id="pp-ocrv6",
                    name="PP-OCRv6",
                    languages=("en",),
                    description="Official PaddleOCR PP-OCRv6 general OCR pipeline.",
                ),
                ModelCapability(
                    id="pp-ocrv5",
                    name="PP-OCRv5",
                    languages=("en", "ru"),
                    description="Official PaddleOCR PP-OCRv5 pipeline, including Russian support.",
                ),
            ),
            DOCUMENT_TASK: (
                ModelCapability(
                    id="pp-structurev3",
                    name="PP-StructureV3",
                    languages=("en", "ru"),
                    description="Official PaddleOCR document layout, table, formula and Markdown pipeline.",
                    output_formats=("json", "markdown", "both"),
                ),
            ),
        }
        self.validate()

    def validate(self) -> None:
        ids = [model.id for models in self._tasks.values() for model in models]
        if len(ids) != len(set(ids)):
            raise ValueError("Capability registry contains duplicate model identifiers")
        if any(not model.languages for models in self._tasks.values() for model in models):
            raise ValueError("Every model must support at least one language")

    def validate_defaults(self, settings: Settings) -> None:
        self.resolve(OCR_TASK, settings.default_ocr_model, settings.default_ocr_language)
        self.resolve(DOCUMENT_TASK, settings.default_parser_model, settings.default_parser_language)

    def resolve(
        self, task: str, model: str | None, language: str | None, settings: Settings | None = None
    ) -> tuple[ModelCapability, str]:
        if task not in self._tasks:
            raise ValueError(f"Unknown task {task}")
        if settings is not None:
            model = model or (settings.default_ocr_model if task == OCR_TASK else settings.default_parser_model)
            language = language or (
                settings.default_ocr_language if task == OCR_TASK else settings.default_parser_language
            )
        if model is None or language is None:
            raise ValueError("Defaults are required when resolve is called without settings")
        selected = next((candidate for candidate in self._tasks[task] if candidate.id == model), None)
        if selected is None:
            known_for_another_task = any(
                model == candidate.id for candidates in self._tasks.values() for candidate in candidates
            )
            if known_for_another_task:
                raise IncompatibleModelTaskError(
                    f"Model '{model}' is not supported for task '{task}'",
                    details={"task": task, "capabilities_endpoint": "/api/v1/capabilities"},
                )
            raise UnsupportedModelError(
                f"Model '{model}' is not supported for task '{task}'",
                details={"task": task, "available_models": [item.id for item in self._tasks[task]]},
            )
        all_languages = {
            item for candidates in self._tasks.values() for candidate in candidates for item in candidate.languages
        }
        if language not in all_languages:
            raise UnsupportedLanguageError(
                f"Language '{language}' is not supported",
                details={"available_languages": sorted(all_languages), "capabilities_endpoint": "/api/v1/capabilities"},
            )
        if language not in selected.languages:
            raise IncompatibleModelLanguageError(
                f"Language '{language}' is not supported by model '{model}'",
                details={"model": model, "available_languages": list(selected.languages)},
            )
        return selected, language

    def validate_output_format(self, output_format: str) -> None:
        if output_format not in {"json", "markdown", "both"}:
            raise UnsupportedOutputFormatError(
                f"Output format '{output_format}' is not supported",
                details={"available_output_formats": ["json", "markdown", "both"]},
            )

    def response(self, settings: Settings) -> CapabilitiesResponse:
        defaults = {
            OCR_TASK: (settings.default_ocr_model, settings.default_ocr_language),
            DOCUMENT_TASK: (settings.default_parser_model, settings.default_parser_language),
        }
        tasks = {}
        for task, models in self._tasks.items():
            task_models = [
                ModelCapabilityResponse(
                    id=model.id,
                    name=model.name,
                    languages=list(model.languages),
                    description=model.description,
                    output_formats=list(model.output_formats) if model.output_formats else None,
                )
                for model in models
            ]
            tasks[task] = TaskCapabilityResponse(
                models=task_models,
                default_model=defaults[task][0],
                default_language=defaults[task][1],
                supported_mime_types=list(SUPPORTED_MIME_TYPES),
                supported_extensions=list(SUPPORTED_EXTENSIONS),
                max_upload_size_mb=settings.max_upload_size_mb,
                max_pdf_pages=settings.max_pdf_pages,
            )
        return CapabilitiesResponse(tasks=tasks)
