"""Клиент OCR API, получающий поддерживаемые параметры только из capabilities."""

from __future__ import annotations

import logging
import random
import time
from threading import BoundedSemaphore
from typing import Any

import httpx

from ..config import OCRSettings
from ..exceptions import ExternalServiceError, OCRServiceError, PermanentError
from ..logging import log_event

LOGGER = logging.getLogger(__name__)


class OCRClient:
    def __init__(self, settings: OCRSettings) -> None:
        self.settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(
                settings.timeout_seconds, connect=15, read=settings.timeout_seconds, write=30, pool=15
            ),
        )
        self._capabilities: dict[str, Any] | None = None
        self._capabilities_at = 0.0
        self._semaphore = BoundedSemaphore(settings.max_concurrent_requests)

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            started = time.perf_counter()
            http_status: int | None = None
            try:
                with self._semaphore:
                    response = self._client.request(method, url, **kwargs)
                http_status = response.status_code
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise OCRServiceError(f"OCR временно недоступен (HTTP {response.status_code}).")
                response.raise_for_status()
                log_event(
                    LOGGER,
                    "ocr_request_completed",
                    component="ocr_client",
                    service="ocr",
                    operation=url,
                    http_method=method,
                    http_status=http_status,
                    attempt=attempt + 1,
                    max_attempts=self.settings.max_retries + 1,
                    duration_ms=round((time.perf_counter() - started) * 1000),
                )
                return response
            except (httpx.HTTPError, ExternalServiceError) as exc:
                last_error = exc
                retryable = attempt < self.settings.max_retries
                log_event(
                    LOGGER,
                    "ocr_request_failed",
                    level=logging.WARNING if retryable else logging.ERROR,
                    component="ocr_client",
                    service="ocr",
                    operation=url,
                    http_method=method,
                    http_status=http_status,
                    attempt=attempt + 1,
                    max_attempts=self.settings.max_retries + 1,
                    retryable=retryable,
                    error_type=type(exc).__name__,
                    duration_ms=round((time.perf_counter() - started) * 1000),
                )
                if retryable:
                    time.sleep(min(15, 0.5 * 2**attempt) + random.uniform(0, 0.25))
        log_event(
            LOGGER,
            "ocr_request_exhausted",
            level=logging.ERROR,
            component="ocr_client",
            service="ocr",
            operation=url,
            http_method=method,
            max_attempts=self.settings.max_retries + 1,
            error_type=type(last_error).__name__ if last_error else "UnknownError",
        )
        raise OCRServiceError("OCR не ответил после ограниченного числа повторов.") from last_error

    def health(self) -> bool:
        return self._client.get("health/ready").is_success

    def capabilities(self, *, refresh: bool = False) -> dict[str, Any]:
        if (
            not refresh
            and self._capabilities
            and time.monotonic() - self._capabilities_at < self.settings.capabilities_cache_ttl_seconds
        ):
            return self._capabilities
        try:
            payload = self._request("GET", "api/v1/capabilities").json()
        except ValueError as exc:
            raise OCRServiceError("OCR вернул некорректный JSON capabilities.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), dict):
            raise OCRServiceError("OCR capabilities не соответствуют контракту.")
        self._capabilities, self._capabilities_at = payload, time.monotonic()
        return payload

    def process(
        self, file_name: str, data: bytes, mime: str, *, task: str, model: str, language: str, output_format: str | None
    ) -> dict[str, Any]:
        if task not in {"ocr", "document_parsing"}:
            raise PermanentError("Выбранная OCR-задача не поддерживается.")
        endpoint = "api/v1/ocr" if task == "ocr" else "api/v1/documents/parse"
        fields: dict[str, str] = {"model": model, "language": language}
        if task == "ocr":
            fields.update({"return_boxes": "true", "return_confidence": "true"})
        else:
            fields["output_format"] = output_format or "json"
        started = time.perf_counter()
        log_event(
            LOGGER,
            "ocr_processing_started",
            component="ocr_client",
            service="ocr",
            operation="process",
            task=task,
            ocr_model=model,
            language=language,
            input_bytes=len(data),
        )
        response = self._request("POST", endpoint, data=fields, files={"file": (file_name, data, mime)})
        try:
            result = response.json()
        except ValueError as exc:
            raise OCRServiceError("OCR вернул некорректный JSON.") from exc
        if not isinstance(result, dict):
            raise OCRServiceError("OCR вернул неожиданный ответ.")
        log_event(
            LOGGER,
            "ocr_processing_completed",
            component="ocr_client",
            service="ocr",
            operation="process",
            task=task,
            ocr_model=model,
            language=language,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        return result
