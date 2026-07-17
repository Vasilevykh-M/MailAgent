"""Safe, domain-specific errors exposed by the HTTP API."""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """Base class for expected service failures."""

    status_code = 400
    code = "service_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationServiceError(ServiceError):
    status_code = 422


class UnsupportedModelError(ValidationServiceError):
    code = "unsupported_model"


class UnsupportedLanguageError(ValidationServiceError):
    code = "unsupported_language"


class IncompatibleModelLanguageError(ValidationServiceError):
    code = "incompatible_model_language"


class IncompatibleModelTaskError(ValidationServiceError):
    code = "incompatible_model_task"


class UnsupportedOutputFormatError(ValidationServiceError):
    code = "unsupported_output_format"


class UnsupportedFileError(ServiceError):
    status_code = 415
    code = "unsupported_file_format"


class EmptyFileError(ServiceError):
    status_code = 422
    code = "empty_file"


class OversizedFileError(ServiceError):
    status_code = 413
    code = "file_too_large"


class CorruptedImageError(ServiceError):
    status_code = 422
    code = "corrupted_image"


class CorruptedPdfError(ServiceError):
    status_code = 422
    code = "corrupted_pdf"


class PdfPageLimitError(ServiceError):
    status_code = 422
    code = "pdf_page_limit_exceeded"


class ModelLoadError(ServiceError):
    status_code = 503
    code = "model_loading_failed"


class ModelDownloadError(ServiceError):
    status_code = 503
    code = "model_download_failed"


class InsufficientMemoryError(ServiceError):
    status_code = 503
    code = "insufficient_system_memory"


class InsufficientGpuMemoryError(ServiceError):
    status_code = 503
    code = "insufficient_gpu_memory"


class UnavailableDeviceError(ServiceError):
    status_code = 503
    code = "unavailable_device"


class InferenceError(ServiceError):
    status_code = 502
    code = "inference_failed"


class InferenceTimeoutError(ServiceError):
    status_code = 504
    code = "inference_timeout"
