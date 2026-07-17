"""Task orchestration independent of FastAPI route implementations."""

from __future__ import annotations

import logging
import time

from fastapi import UploadFile

from app.core.config import Settings
from app.schemas.documents import DocumentParseResponse
from app.schemas.ocr import OcrResponse
from app.services.capabilities import DOCUMENT_TASK, OCR_TASK, CapabilitiesRegistry
from app.services.file_processor import FileProcessor
from app.services.inference_limiter import InferenceLimiter
from app.services.model_manager import ModelManager
from app.services.normalizers import normalize_document, normalize_ocr

logger = logging.getLogger(__name__)


class ProcessingService:
    def __init__(
        self,
        settings: Settings,
        registry: CapabilitiesRegistry,
        files: FileProcessor,
        models: ModelManager,
        limiter: InferenceLimiter,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._files = files
        self._models = models
        self._limiter = limiter

    async def ocr(
        self,
        upload: UploadFile,
        *,
        request_id: str,
        model: str | None,
        language: str | None,
        return_boxes: bool,
        return_confidence: bool,
    ) -> OcrResponse:
        selected, selected_language = self._registry.resolve(OCR_TASK, model, language, self._settings)
        started = time.perf_counter()
        document = await self._files.prepare(upload)
        async with self._files.inference_input(document) as input_value:
            lease = await self._models.acquire(OCR_TASK, selected.id, selected_language)
            try:
                raw, wait_ms, inference_ms = await self._limiter.run(
                    lease.loaded.inference_lock,
                    lambda: lease.loaded.adapter.predict(lease.loaded.pipeline, input_value),
                )
            finally:
                await lease.release()
        processing_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "ocr_completed request_id=%s task=ocr model=%s language=%s device=%s file_size=%s page_count=%s "
            "semaphore_wait_ms=%s model_loading_time_ms=%s inference_time_ms=%s cache_hit=%s processing_time_ms=%s",
            request_id,
            selected.id,
            selected_language,
            self._settings.paddle_device,
            len(document.data),
            document.page_count,
            wait_ms,
            lease.load_time_ms,
            inference_ms,
            lease.cache_hit,
            processing_ms,
        )
        return normalize_ocr(
            raw,
            document,
            request_id=request_id,
            model=selected.id,
            language=selected_language,
            return_boxes=return_boxes,
            return_confidence=return_confidence,
            processing_time_ms=processing_ms,
        )

    async def document_parse(
        self,
        upload: UploadFile,
        *,
        request_id: str,
        model: str | None,
        language: str | None,
        output_format: str,
    ) -> DocumentParseResponse:
        self._registry.validate_output_format(output_format)
        selected, selected_language = self._registry.resolve(DOCUMENT_TASK, model, language, self._settings)
        started = time.perf_counter()
        document = await self._files.prepare(upload)
        async with self._files.inference_input(document) as input_value:
            lease = await self._models.acquire(DOCUMENT_TASK, selected.id, selected_language)
            try:
                raw, wait_ms, inference_ms = await self._limiter.run(
                    lease.loaded.inference_lock,
                    lambda: lease.loaded.adapter.predict(lease.loaded.pipeline, input_value),
                )
            finally:
                await lease.release()
        processing_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "document_parse_completed request_id=%s task=document_parsing model=%s language=%s device=%s file_size=%s "
            "page_count=%s semaphore_wait_ms=%s model_loading_time_ms=%s "
            "inference_time_ms=%s cache_hit=%s processing_time_ms=%s",
            request_id,
            selected.id,
            selected_language,
            self._settings.paddle_device,
            len(document.data),
            document.page_count,
            wait_ms,
            lease.load_time_ms,
            inference_ms,
            lease.cache_hit,
            processing_ms,
        )
        return normalize_document(
            raw,
            document,
            request_id=request_id,
            model=selected.id,
            language=selected_language,
            output_format=output_format,
            processing_time_ms=processing_ms,
        )
