"""The small boundary between public service code and PaddleOCR pipelines."""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol

from app.core.config import Settings
from app.core.exceptions import (
    InferenceError,
    InsufficientGpuMemoryError,
    InsufficientMemoryError,
    ModelDownloadError,
    ModelLoadError,
    UnavailableDeviceError,
)
from app.services.capabilities import DOCUMENT_TASK, OCR_TASK

logger = logging.getLogger(__name__)


class PipelineAdapter(Protocol):
    task: str

    def create(self, model: str, language: str, settings: Settings) -> Any: ...

    def predict(self, pipeline: Any, input_value: Any, **parameters: Any) -> list[Any]: ...

    def release(self, pipeline: Any) -> None: ...


class PaddleOcrAdapter:
    task = OCR_TASK
    _MODEL_VERSIONS = {"pp-ocrv6": "PP-OCRv6", "pp-ocrv5": "PP-OCRv5"}

    def create(self, model: str, language: str, settings: Settings) -> Any:
        self._configure_cache(settings)
        try:
            from paddleocr import PaddleOCR

            logger.info(
                "paddle_pipeline_initializing task=ocr model=%s language=%s device=%s enable_mkldnn=%s",
                model,
                language,
                settings.paddle_device,
                settings.paddle_enable_mkldnn,
            )
            return PaddleOCR(
                lang=language,
                ocr_version=self._MODEL_VERSIONS[model],
                device=settings.paddle_device,
                enable_mkldnn=settings.paddle_enable_mkldnn,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except ImportError as exc:
            raise ModelLoadError("PaddleOCR is not installed correctly") from exc
        except Exception as exc:
            logger.exception("model_load_failed task=ocr model=%s language=%s", model, language)
            raise _load_error(exc, "The OCR model could not be initialized") from exc

    def predict(self, pipeline: Any, input_value: Any, **parameters: Any) -> list[Any]:
        try:
            return list(pipeline.predict(input_value, **parameters))
        except Exception as exc:
            logger.exception("inference_failed task=ocr")
            raise _inference_error(exc, "OCR inference failed") from exc

    @staticmethod
    def _configure_cache(settings: Settings) -> None:
        # PaddleX 3.7 uses this official cache environment variable. It is set
        # before importing PaddleOCR, whose dependency imports PaddleX lazily.
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(settings.paddle_model_home)
        os.environ["PADDLE_PDX_MODEL_SOURCE"] = settings.paddle_model_source

    @staticmethod
    def release(pipeline: Any) -> None:
        close = getattr(pipeline, "close", None)
        if callable(close):
            close()


class PaddleDocumentParserAdapter:
    task = DOCUMENT_TASK

    def create(self, model: str, language: str, settings: Settings) -> Any:
        if model != "pp-structurev3":
            raise ModelLoadError("The requested document model cannot be initialized")
        PaddleOcrAdapter._configure_cache(settings)
        try:
            from paddleocr import PPStructureV3

            logger.info(
                "paddle_pipeline_initializing task=document_parsing model=%s language=%s device=%s enable_mkldnn=%s",
                model,
                language,
                settings.paddle_device,
                settings.paddle_enable_mkldnn,
            )
            return PPStructureV3(
                lang=language,
                ocr_version="PP-OCRv5",
                device=settings.paddle_device,
                enable_mkldnn=settings.paddle_enable_mkldnn,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except ImportError as exc:
            raise ModelLoadError("PaddleOCR document parsing dependencies are not installed correctly") from exc
        except Exception as exc:
            logger.exception("model_load_failed task=document_parsing model=%s language=%s", model, language)
            raise _load_error(exc, "The document parsing model could not be initialized") from exc

    def predict(self, pipeline: Any, input_value: Any, **parameters: Any) -> list[Any]:
        try:
            return list(pipeline.predict(input_value, **parameters))
        except Exception as exc:
            logger.exception("inference_failed task=document_parsing")
            raise _inference_error(exc, "Document parsing inference failed") from exc

    @staticmethod
    def release(pipeline: Any) -> None:
        PaddleOcrAdapter.release(pipeline)


def _load_error(exc: Exception, fallback: str) -> ModelLoadError | ModelDownloadError | UnavailableDeviceError:
    message = str(exc).lower()
    if any(token in message for token in ("download", "huggingface", "modelscope", "connection")):
        return ModelDownloadError("The model could not be downloaded or found in the persistent model directory")
    if any(token in message for token in ("device", "cuda", "gpu")):
        return UnavailableDeviceError("The configured inference device is unavailable")
    return ModelLoadError(fallback)


def _inference_error(
    exc: Exception, fallback: str
) -> InferenceError | InsufficientMemoryError | InsufficientGpuMemoryError | UnavailableDeviceError:
    message = str(exc).lower()
    if isinstance(exc, MemoryError) or "out of memory" in message:
        if any(token in message for token in ("gpu", "cuda", "cudnn")):
            return InsufficientGpuMemoryError("The configured GPU has insufficient memory for this inference")
        return InsufficientMemoryError("The system has insufficient memory for this inference")
    if any(token in message for token in ("device unavailable", "no cuda", "cannot use gpu")):
        return UnavailableDeviceError("The configured inference device is unavailable")
    return InferenceError(fallback)


class AdapterFactory:
    """Creates task-specific adapters without exposing PaddleOCR to routers."""

    def __init__(self) -> None:
        self._adapters: dict[str, PipelineAdapter] = {
            OCR_TASK: PaddleOcrAdapter(),
            DOCUMENT_TASK: PaddleDocumentParserAdapter(),
        }

    def for_task(self, task: str) -> PipelineAdapter:
        return self._adapters[task]
