"""Идемпотентная загрузка: S3 сначала, PostgreSQL-транзакция после проверки HEAD."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from datetime import UTC
from typing import Any, Protocol

from starlette.datastructures import UploadFile

from ..db import AttachmentObject, CommitResult
from ..errors import ConflictError, RetryableStorageError, ValidationAPIError
from ..schemas import FileMetadata, IngestionPayload, IngestionResponse
from ..storage.s3 import ObjectStorage, attachment_key, raw_key


class CommitRepository(Protocol):
    async def commit(
        self, payload: IngestionPayload, raw: Any, attachments: list[AttachmentObject]
    ) -> CommitResult: ...


def _size_and_hash(upload: UploadFile) -> tuple[int, str]:
    stream = upload.file
    stream.seek(0)
    size, digest = 0, hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        digest.update(chunk)
    stream.seek(0)
    return size, digest.hexdigest()


class IngestionService:
    def __init__(
        self, *, repository: CommitRepository, storage: ObjectStorage, max_message_bytes: int, max_attachment_bytes: int
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.max_message_bytes = max_message_bytes
        self.max_attachment_bytes = max_attachment_bytes

    @staticmethod
    def _results_by_hash(payload: IngestionPayload) -> dict[str, dict[str, Any]]:
        values = payload.agent_result.get("attachments", [])
        if not isinstance(values, list):
            return {}
        return {
            str(item["sha256"]): item
            for item in values
            if isinstance(item, dict) and isinstance(item.get("sha256"), str)
        }

    @staticmethod
    def _assert_mapping(metadata: list[FileMetadata], uploads: Mapping[str, UploadFile]) -> None:
        expected = {entry.part_name for entry in metadata}
        actual = set(uploads)
        if expected != actual:
            raise ValidationAPIError("Multipart file mapping does not match payload.files")

    async def ingest(
        self,
        payload: IngestionPayload,
        *,
        raw_email: UploadFile,
        attachments: Mapping[str, UploadFile],
    ) -> IngestionResponse:
        self._assert_mapping(payload.files, attachments)
        raw_size, raw_digest = await asyncio.to_thread(_size_and_hash, raw_email)
        if raw_size > self.max_message_bytes:
            raise ValidationAPIError("Raw email exceeds size limit")
        raw = await asyncio.to_thread(
            self.storage.put_verified,
            raw_email.file,
            key=raw_key(payload.received_at, payload.record_id),
            expected_size=raw_size,
            expected_sha256=raw_digest,
            content_type="message/rfc822",
        )
        processed = self._results_by_hash(payload)
        stored: list[AttachmentObject] = []
        for position, metadata in enumerate(payload.files):
            upload = attachments[metadata.part_name]
            if metadata.size > self.max_attachment_bytes:
                raise ValidationAPIError("Attachment exceeds size limit")
            actual_size, actual_digest = await asyncio.to_thread(_size_and_hash, upload)
            if actual_size != metadata.size or actual_digest != metadata.sha256:
                raise ValidationAPIError("Attachment does not match declared metadata")
            object_item = await asyncio.to_thread(
                self.storage.put_verified,
                upload.file,
                key=attachment_key(payload.received_at, payload.record_id, metadata.sha256, metadata.safe_filename),
                expected_size=metadata.size,
                expected_sha256=metadata.sha256,
                content_type=metadata.detected_content_type,
            )
            stored.append(
                AttachmentObject(
                    position=position,
                    metadata=metadata.model_dump(mode="json"),
                    storage=object_item,
                    processing_result=processed.get(metadata.sha256),
                )
            )
        try:
            committed = await self.repository.commit(payload, raw, stored)
        except ConflictError:
            raise
        except Exception as exc:
            # Объекты могут остаться сиротами, но без PostgreSQL записи они недоступны извне.
            raise RetryableStorageError() from exc
        return IngestionResponse(
            record_id=payload.record_id,
            processing_generation=payload.processing_generation,
            attachment_count=len(stored),
            storage_verified=True,
            committed_at=committed.committed_at.astimezone(UTC),
        )
