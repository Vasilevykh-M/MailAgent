"""Типизированный потоковый клиент независимого Results API."""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ..config import ResultsAPISettings
from ..exceptions import ResultsAPIError, ResultsAPIPermanentError
from ..logging import log_event

LOGGER = logging.getLogger(__name__)


class ResultCommit(BaseModel):
    record_id: str
    status: str
    processing_generation: int = Field(ge=0)
    attachment_count: int = Field(ge=0)
    storage_verified: bool
    committed_at: str


class ResultsAPIClient:
    """Передаёт открытые file handles в httpx, не логируя пользовательские данные и секреты."""

    def __init__(self, settings: ResultsAPISettings) -> None:
        self.settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url.rstrip("/"),
            timeout=httpx.Timeout(settings.timeout_seconds, connect=min(30, settings.timeout_seconds)),
            verify=settings.verify_tls,
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> bool:
        return self._client.get("/health/ready").status_code == 200

    @staticmethod
    def _retryable(status_code: int) -> bool:
        return status_code in {408, 425, 429} or status_code >= 500

    def persist(
        self,
        payload: Mapping[str, Any],
        *,
        raw_email_path: Path,
        attachment_paths: Mapping[str, str],
    ) -> ResultCommit:
        record = str(payload.get("record_id") or "")
        generation = int(payload.get("processing_generation", 0) or 0)
        if len(record) != 64 or not raw_email_path.is_file():
            raise ResultsAPIPermanentError("Нет корректных данных для сохранения результата.")
        files_value = payload.get("files", [])
        files = files_value if isinstance(files_value, list) else []
        selected: list[tuple[dict[str, Any], Path]] = []
        for entry in files:
            if not isinstance(entry, dict):
                raise ResultsAPIPermanentError("Некорректное описание вложения для Results API.")
            digest = entry.get("sha256")
            file_path = attachment_paths.get(digest) if isinstance(digest, str) else None
            if not isinstance(file_path, str) or not Path(file_path).is_file():
                raise ResultsAPIError("Временный файл вложения недоступен для отправки.")
            selected.append((entry, Path(file_path)))
        encoded = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":"), default=str)
        for attempt in range(self.settings.max_retries + 1):
            try:
                with raw_email_path.open("rb") as raw_handle:
                    handles = [path.open("rb") for _, path in selected]
                    try:
                        multipart: list[tuple[str, tuple[Any, ...]]] = [
                            ("payload", (None, encoded, "application/json")),
                            ("raw_email", ("original.eml", raw_handle, "message/rfc822")),
                        ]
                        for metadata, handle in zip((entry for entry, _path in selected), handles, strict=True):
                            multipart.append(
                                (
                                    str(metadata["part_name"]),
                                    (
                                        str(metadata.get("safe_filename") or "attachment.bin"),
                                        handle,
                                        "application/octet-stream",
                                    ),
                                )
                            )
                        response = self._client.put(
                            f"/api/v1/internal/emails/{record}",
                            files=multipart,
                            headers={
                                "X-API-Key": self.settings.api_key,
                                "X-Request-ID": str(uuid.uuid4()),
                                "Idempotency-Key": record,
                            },
                        )
                    finally:
                        for handle in handles:
                            handle.close()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                if attempt == self.settings.max_retries:
                    raise ResultsAPIError("Results API временно недоступен.") from exc
                self._sleep(attempt)
                continue
            if self._retryable(response.status_code):
                if attempt == self.settings.max_retries:
                    raise ResultsAPIError("Results API не подтвердил сохранение результата.")
                self._sleep(attempt)
                continue
            if response.status_code >= 400:
                raise ResultsAPIPermanentError("Results API отклонил результат обработки.")
            try:
                committed = ResultCommit.model_validate(response.json())
            except Exception as exc:
                raise ResultsAPIError("Results API вернул некорректное подтверждение.") from exc
            if (
                committed.record_id != record
                or committed.processing_generation != generation
                or committed.status != "committed"
                or not committed.storage_verified
            ):
                raise ResultsAPIError("Results API не подтвердил ожидаемый результат.")
            log_event(
                LOGGER,
                "results_api_commit_confirmed",
                component="results_api",
                record_id=record,
                attachment_count=committed.attachment_count,
            )
            return committed
        raise ResultsAPIError("Results API не подтвердил сохранение результата.")  # pragma: no cover

    @staticmethod
    def _sleep(attempt: int) -> None:
        time.sleep(min(30.0, 0.5 * (2**attempt)) + random.uniform(0, 0.25))
