from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import CommitResult
from app.errors import ConflictError, NotFoundError
from app.main import create_app
from app.schemas import EmailListItem, IngestionPayload
from app.storage.s3 import StoredObject

RECORD_ID = "a" * 64


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_verified(
        self, source, *, key: str, expected_size: int, expected_sha256: str, content_type: str
    ) -> StoredObject:
        source.seek(0)
        data = source.read()
        assert len(data) == expected_size
        assert hashlib.sha256(data).hexdigest() == expected_sha256
        self.objects[key] = (data, content_type)
        return StoredObject("mail-agent", key, "etag", None, len(data), content_type)

    def head(self, key: str) -> StoredObject:
        if key not in self.objects:
            raise NotFoundError()
        data, content_type = self.objects[key]
        return StoredObject("mail-agent", key, "etag", None, len(data), content_type)

    def stream(self, key: str):
        yield self.objects[key][0]

    def ready(self) -> bool:
        return True


class MemoryRepository:
    def __init__(self) -> None:
        self.payloads: dict[str, IngestionPayload] = {}
        self.attachments: dict[str, list[object]] = {}
        self.raw_keys: dict[str, str] = {}

    async def commit(self, payload, raw, attachments):
        current = self.payloads.get(payload.record_id)
        if current is not None:
            if payload.processing_generation < current.processing_generation:
                raise ConflictError()
            if (
                payload.processing_generation == current.processing_generation
                and payload.fingerprint() != current.fingerprint()
            ):
                raise ConflictError()
        self.payloads[payload.record_id] = payload
        self.attachments[payload.record_id] = list(attachments)
        self.raw_keys[payload.record_id] = raw.key
        return CommitResult(datetime(2026, 7, 17, tzinfo=UTC), idempotent=current is not None)

    async def list_month(self, _month, *, limit, cursor, mailbox=None):
        values = [
            EmailListItem(
                record_id="b" * 64,
                received_at=datetime(2026, 7, 17, tzinfo=UTC),
                **{"from": "sender@example.test"},
                subject="Тема",
                summary_preview="Кратко",
                attachment_count=1,
                confidence=0.9,
            ),
            EmailListItem(
                record_id="c" * 64,
                received_at=datetime(2026, 7, 16, tzinfo=UTC),
                **{"from": "sender@example.test"},
                subject="Ещё тема",
                summary_preview="Кратко",
                attachment_count=0,
                confidence=0.8,
            ),
        ]
        return values[:limit]

    async def detail(self, record_id):
        payload = self.payloads.get(record_id)
        if payload is None:
            raise NotFoundError()
        email = SimpleNamespace(
            record_id=payload.record_id,
            received_at=payload.received_at,
            processed_at=payload.processed_at,
            mailbox=payload.mailbox,
            uid=payload.uid,
            message_id=payload.message_id,
            pipeline_version=payload.pipeline_version,
            processing_generation=payload.processing_generation,
            original_email=payload.original_email.model_dump(mode="json", by_alias=True),
            agent_result=payload.agent_result,
            raw_key=self.raw_keys[record_id],
            raw_size=len(b"From: sender\r\n\r\nbody"),
        )
        values = []
        for item in self.attachments[record_id]:
            metadata = item.metadata
            values.append(
                SimpleNamespace(
                    attachment_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{record_id}:{item.position}"),
                    position=item.position,
                    original_filename=metadata["original_filename"],
                    safe_filename=metadata["safe_filename"],
                    content_type=metadata["content_type"],
                    detected_content_type=metadata["detected_content_type"],
                    size=metadata["size"],
                    sha256=metadata["sha256"],
                    is_inline=metadata["is_inline"],
                    content_id=metadata["content_id"],
                    processing_result=item.processing_result,
                    object_key=item.storage.key,
                )
            )
        return email, values

    async def attachment(self, record_id, attachment_id):
        _email, attachments = await self.detail(record_id)
        for item in attachments:
            if item.attachment_id == attachment_id:
                return item
        raise NotFoundError()


def payload_for(attachment: bytes = b"document") -> dict[str, object]:
    attachment_sha256 = hashlib.sha256(attachment).hexdigest()
    return {
        "schema_version": 1,
        "record_id": RECORD_ID,
        "pipeline_version": "2",
        "processing_generation": 0,
        "mailbox": "INBOX",
        "uid": "123",
        "message_id": "<id@example.test>",
        "received_at": "2026-07-17T10:00:00Z",
        "processed_at": "2026-07-17T10:03:00Z",
        "original_email": {
            "subject": "Тема",
            "from": "sender@example.test",
            "to": ["to@example.test"],
            "headers": [{"name": "X-Repeat", "value": "one"}, {"name": "X-Repeat", "value": "two"}],
            "text_plain": "text",
            "text_html": "<p>text</p>",
            "normalized_body": "text",
        },
        "agent_result": {
            "summary": {
                "summary_ru": "Итог",
                "classification": {"class_code": "MACHINES", "class_name_ru": "Станки"},
                "key_facts_ru": ["Срок поставки до 25 июля"],
                "attachment_summaries": ["original.pdf: коммерческое предложение"],
                "warnings_ru": ["Проверить срок поставки"],
                "confidence": 0.9,
            },
            "attachments": [
                {
                    "sha256": attachment_sha256,
                    "summary_ru": "Коммерческое предложение на станок",
                    "key_facts_ru": ["Указан срок поставки"],
                }
            ],
            "warnings": ["Вложение обработано автоматически"],
        },
        "files": [
            {
                "part_name": "attachment_0",
                "original_filename": "original.pdf",
                "safe_filename": "document.pdf",
                "content_type": "application/pdf",
                "detected_content_type": "application/pdf",
                "size": len(attachment),
                "sha256": attachment_sha256,
                "is_inline": False,
            }
        ],
    }


def client(*, allow_anonymous_reader: bool = False) -> tuple[TestClient, MemoryRepository, MemoryStorage]:
    settings = Settings(writer_api_key="writer", reader_api_key="reader", allow_anonymous_reader=allow_anonymous_reader)
    repository, storage = MemoryRepository(), MemoryStorage()
    return TestClient(create_app(settings, repository=repository, storage=storage)), repository, storage


def files(payload: dict[str, object], attachment: bytes = b"document") -> dict[str, tuple[object, ...]]:
    return {
        "payload": (None, json.dumps(payload), "application/json"),
        "raw_email": ("original.eml", io.BytesIO(b"From: sender\r\n\r\nbody"), "message/rfc822"),
        "attachment_0": ("document.pdf", io.BytesIO(attachment), "application/pdf"),
    }


def writer_headers() -> dict[str, str]:
    return {"X-API-Key": "writer", "Idempotency-Key": RECORD_ID, "X-Request-ID": "request-test"}


def test_writer_auth_mapping_sha_and_idempotency() -> None:
    test_client, repository, storage = client()
    payload = payload_for()
    denied = test_client.put(f"/api/v1/internal/emails/{RECORD_ID}", files=files(payload))
    assert denied.status_code == 401
    assert denied.json()["error"] == "unauthorized"
    response = test_client.put(f"/api/v1/internal/emails/{RECORD_ID}", files=files(payload), headers=writer_headers())
    assert response.status_code == 200
    assert response.json()["storage_verified"] is True
    assert response.headers["X-Request-ID"] == "request-test"
    assert len(repository.attachments[RECORD_ID]) == 1
    assert len(storage.objects) == 2
    replay = test_client.put(f"/api/v1/internal/emails/{RECORD_ID}", files=files(payload), headers=writer_headers())
    assert replay.status_code == 200
    changed = payload_for(b"changed")
    conflict = test_client.put(
        f"/api/v1/internal/emails/{RECORD_ID}", files=files(changed, b"changed"), headers=writer_headers()
    )
    assert conflict.status_code == 409


def test_invalid_mapping_and_safe_errors() -> None:
    test_client, _repository, _storage = client()
    response = test_client.put(
        f"/api/v1/internal/emails/{RECORD_ID}",
        files={"payload": (None, json.dumps(payload_for()), "application/json"), "raw_email": ("a.eml", b"x")},
        headers=writer_headers(),
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_payload"
    assert "original.pdf" not in response.text


def test_anonymous_reader_does_not_allow_anonymous_writer() -> None:
    test_client, _repository, _storage = client(allow_anonymous_reader=True)

    reader_response = test_client.get("/api/v1/emails?limit=1")
    assert reader_response.status_code == 200
    writer_response = test_client.put(f"/api/v1/internal/emails/{RECORD_ID}", files=files(payload_for()))
    assert writer_response.status_code == 401


def test_reader_list_and_detail_stream_without_storage_url() -> None:
    test_client, _repository, _storage = client()
    list_response = test_client.get("/api/v1/emails?limit=1", headers={"Authorization": "Bearer reader"})
    assert list_response.status_code == 200
    list_item = list_response.json()["items"][0]
    assert list_item["id"] == list_item["record_id"]
    assert list_item["subject"] == "Тема"
    assert list_response.json()["has_more"]
    payload = payload_for()
    assert (
        test_client.put(
            f"/api/v1/internal/emails/{RECORD_ID}", files=files(payload), headers=writer_headers()
        ).status_code
        == 200
    )
    detail = test_client.get(f"/api/v1/emails/{RECORD_ID}", headers={"X-API-Key": "reader"})
    assert detail.status_code == 200
    data = detail.json()
    assert "minio" not in detail.text.lower()
    assert data["id"] == RECORD_ID
    assert data["subject"] == "Тема"
    assert data["from"] == "sender@example.test"
    assert data["content"] == "text"
    assert data["summary"] == "Итог"
    assert data["classification"]["class_code"] == "MACHINES"
    assert data["key_facts"] == ["Срок поставки до 25 июля"]
    assert data["attachment_summaries"] == ["original.pdf: коммерческое предложение"]
    assert data["attachments"][0]["id"] == data["attachments"][0]["attachment_id"]
    assert data["attachments"][0]["filename"] == "original.pdf"
    assert data["attachments"][0]["summary"] == "Коммерческое предложение на станок"
    assert data["attachments"][0]["key_facts"] == ["Указан срок поставки"]
    assert data["original_email"]["headers"] == [
        {"name": "X-Repeat", "value": "one"},
        {"name": "X-Repeat", "value": "two"},
    ]
    attachment = test_client.get(data["attachments"][0]["download_url"], headers={"X-API-Key": "reader"})
    assert attachment.content == b"document"
    raw = test_client.get(data["raw_download_url"], headers={"X-API-Key": "reader"})
    assert raw.headers["content-type"].startswith("message/rfc822")
    assert raw.content == b"From: sender\r\n\r\nbody"
