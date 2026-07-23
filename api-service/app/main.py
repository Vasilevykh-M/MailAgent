"""FastAPI-приложение Results API без выдачи прямых MinIO URL."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.datastructures import UploadFile

from .auth.repository import AuthRepository
from .auth.router import create_auth_router
from .auth.service import AuthenticationService
from .config import Settings, get_settings
from .db import Attachment, Database, ResultRepository
from .errors import APIError, ValidationAPIError
from .schemas import (
    AttachmentResponse,
    EmailDetail,
    EmailListItem,
    EmailListResponse,
    IngestionPayload,
    IngestionResponse,
    OriginalEmail,
    StatisticsResponse,
    decode_cursor,
    encode_cursor,
)
from .security import require_reader, require_writer
from .services.ingestion import IngestionService
from .storage.s3 import ObjectStorage, S3Storage

LOGGER = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", ""))


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _attachment_response(record_id: str, value: Attachment) -> AttachmentResponse:
    processing_result = _mapping(value.processing_result)
    return AttachmentResponse(
        attachment_id=str(value.attachment_id),
        id=str(value.attachment_id),
        position=value.position,
        original_filename=value.original_filename,
        safe_filename=value.safe_filename,
        filename=value.original_filename or value.safe_filename,
        content_type=value.content_type,
        detected_content_type=value.detected_content_type,
        size=value.size,
        sha256=value.sha256,
        is_inline=value.is_inline,
        content_id=value.content_id,
        summary=_text(processing_result.get("summary_ru")) or None,
        key_facts=_strings(processing_result.get("key_facts_ru")),
        processing_result=processing_result or None,
        download_url=f"/api/v1/emails/{record_id}/attachments/{value.attachment_id}/content",
    )


def _safe_filename_header(value: str) -> str:
    # Значение предварительно санитизировано и хранится в PostgreSQL, но header всё равно кодируется.
    return f"attachment; filename*=UTF-8''{quote(value, safe='')}"


def create_app(
    settings: Settings | None = None,
    *,
    repository: ResultRepository | None = None,
    storage: ObjectStorage | None = None,
    auth_repository: AuthRepository | None = None,
) -> FastAPI:
    selected = settings or get_settings()
    if repository is None:
        concrete_database = Database(selected)
        database: Database | None = concrete_database
        result_repository: ResultRepository = ResultRepository(concrete_database)
    else:
        database = None
        result_repository = repository
    object_storage = storage or S3Storage(selected)
    selected_auth_repository = auth_repository or (AuthRepository(database.sessions) if database is not None else None)
    authentication_service = (
        AuthenticationService(selected_auth_repository, selected) if selected_auth_repository is not None else None
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            if selected.administrator_bootstrap_enabled:
                if authentication_service is None:
                    raise RuntimeError("Authentication administrator bootstrap requires a database repository")
                try:
                    outcome = await authentication_service.bootstrap_administrator()
                except Exception:
                    LOGGER.error("Authentication administrator bootstrap failed")
                    raise
                if outcome is not None:
                    if outcome.created:
                        LOGGER.info("Authentication administrator created")
                    elif outcome.password_changed or outcome.reactivated:
                        LOGGER.info("Authentication administrator synchronized")
                    else:
                        LOGGER.info("Authentication administrator already up to date")
            yield
        finally:
            if database is not None:
                await database.close()

    app = FastAPI(title="Mail Agent Results API", version="1", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=selected.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Content-Length", "X-Request-ID"],
        max_age=600,
    )
    app.state.settings = selected
    app.state.repository = result_repository
    app.state.storage = object_storage
    app.state.database = database
    app.state.authentication_service = authentication_service

    app.include_router(create_auth_router(selected, authentication_service))

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        candidate = request.headers.get("X-Request-ID", "")
        request.state.request_id = candidate if len(candidate) <= 128 and candidate.isprintable() else str(uuid.uuid4())
        try:
            response = await call_next(request)
        except APIError as exc:
            response = JSONResponse(
                {"error": exc.code, "request_id": _request_id(request)}, status_code=exc.status_code
            )
        except Exception:
            LOGGER.exception("Unhandled API error request_id=%s", _request_id(request))
            response = JSONResponse({"error": "internal_error", "request_id": _request_id(request)}, status_code=500)
        response.headers["X-Request-ID"] = _request_id(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        postgres = bool(database is not None and await database.ready())
        minio = await asyncio.to_thread(object_storage.ready)
        status = 200 if postgres and minio else 503
        return JSONResponse({"status": "ok" if status == 200 else "unavailable"}, status_code=status)

    @app.put("/api/v1/internal/emails/{record_id}", response_model=IngestionResponse)
    async def ingest(
        record_id: str,
        request: Request,
        _: None = Depends(require_writer(selected)),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> IngestionResponse:
        max_total = selected.max_message_bytes + selected.max_attachment_bytes * selected.max_attachments_per_message
        declared_length = request.headers.get("Content-Length")
        if declared_length and (not declared_length.isdigit() or int(declared_length) > max_total):
            raise ValidationAPIError("Request exceeds size limit")
        form = await request.form(
            max_files=selected.max_attachments_per_message + 2,
            max_fields=selected.max_attachments_per_message + 8,
            max_part_size=max(selected.max_message_bytes, selected.max_attachment_bytes),
        )
        payload_field = form.get("payload")
        raw_email = form.get("raw_email")
        if not isinstance(payload_field, str) or not isinstance(raw_email, UploadFile):
            raise ValidationAPIError("payload and raw_email are required")
        try:
            payload = IngestionPayload.model_validate_json(payload_field)
        except Exception as exc:
            raise ValidationAPIError("Invalid payload") from exc
        if record_id != payload.record_id or idempotency_key != payload.record_id:
            raise ValidationAPIError("Path and idempotency key must match record_id")
        if len(payload.files) > selected.max_attachments_per_message:
            raise ValidationAPIError("Too many attachments")
        uploads: dict[str, UploadFile] = {}
        repeated = [item for item in form.getlist("attachments") if isinstance(item, UploadFile)]
        for metadata in payload.files:
            item = form.get(metadata.part_name)
            if not isinstance(item, UploadFile):
                # Совместимый вариант повторяемого поля с контролируемым заголовком mapping.
                item = next(
                    (
                        candidate
                        for candidate in repeated
                        if candidate.headers.get("x-file-part-name") == metadata.part_name
                    ),
                    None,
                )
            if not isinstance(item, UploadFile) or metadata.part_name in uploads:
                raise ValidationAPIError("Multipart file mapping does not match payload.files")
            uploads[metadata.part_name] = item
        service = IngestionService(
            repository=result_repository,
            storage=object_storage,
            max_message_bytes=selected.max_message_bytes,
            max_attachment_bytes=selected.max_attachment_bytes,
        )
        try:
            return await service.ingest(payload, raw_email=raw_email, attachments=uploads)
        finally:
            await raw_email.close()
            for upload in uploads.values():
                await upload.close()

    @app.get("/api/v1/emails", response_model=EmailListResponse)
    async def list_emails(
        _: None = Depends(require_reader(selected, authentication_service)),
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: str | None = None,
        from_: Annotated[datetime | None, Query(alias="from")] = None,
        to: datetime | None = None,
        mailbox: str | None = None,
    ) -> EmailListResponse:
        if from_ and to and from_ > to:
            raise ValidationAPIError("Invalid date interval")
        decoded = decode_cursor(cursor) if cursor else None
        moment = decoded[0] if decoded else datetime.now(UTC)
        items: list[EmailListItem] = []
        has_more = False
        # 10 years is a hard upper bound and every query remains a single month partition.
        for _month_index in range(120):
            if from_ and moment < from_:
                break
            needed = limit + 1 - len(items)
            if needed <= 0:
                has_more = True
                break
            page = await result_repository.list_month(moment, limit=needed, cursor=decoded, mailbox=mailbox)
            if from_:
                page = [item for item in page if item.received_at >= from_]
            if to:
                page = [item for item in page if item.received_at <= to]
            items.extend(page)
            if len(items) > limit:
                has_more = True
                items = items[:limit]
                break
            start = moment.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            moment = (
                start.replace(year=start.year - 1, month=12)
                if start.month == 1
                else start.replace(month=start.month - 1)
            )
            decoded = None
        next_cursor = encode_cursor(items[-1].received_at, items[-1].record_id) if items and has_more else None
        return EmailListResponse(items=items, next_cursor=next_cursor, has_more=has_more)

    @app.get("/api/v1/statistics", response_model=StatisticsResponse)
    async def get_statistics(
        from_: Annotated[datetime, Query(alias="from")],
        to: Annotated[datetime, Query()],
        mailbox: str | None = None,
        _: None = Depends(require_reader(selected, authentication_service)),
    ) -> StatisticsResponse:
        if from_.tzinfo is None or to.tzinfo is None:
            raise ValidationAPIError("Statistics period must include a timezone")
        start, end = from_.astimezone(UTC), to.astimezone(UTC)
        if start >= end:
            raise ValidationAPIError("Statistics period must have from before to")
        if end - start > timedelta(days=3660):
            raise ValidationAPIError("Statistics period must not exceed 10 years")
        values = await result_repository.statistics(start, end, mailbox=mailbox)
        return StatisticsResponse.model_validate(
            {
                "from": start,
                "to": end,
                "mailbox": mailbox,
                "total_emails": int(values["total_emails"]),
                "total_attachments": int(values["total_attachments"]),
                "classifications": values["classifications"],
            }
        )

    @app.get("/api/v1/emails/{record_id}", response_model=EmailDetail)
    async def get_email(
        record_id: str, _: None = Depends(require_reader(selected, authentication_service))
    ) -> EmailDetail:
        email, attachments = await result_repository.detail(record_id)
        original_email = OriginalEmail.model_validate(email.original_email)
        agent_result = _mapping(email.agent_result)
        summary = _mapping(agent_result.get("summary"))
        return EmailDetail(
            id=email.record_id,
            subject=original_email.subject,
            **{"from": original_email.sender},
            content=original_email.normalized_body or original_email.text_plain,
            summary=_text(summary.get("summary_ru")),
            classification=_mapping(summary.get("classification")) or None,
            key_facts=_strings(summary.get("key_facts_ru")),
            attachment_summaries=_strings(summary.get("attachment_summaries")),
            warnings=[*_strings(summary.get("warnings_ru")), *_strings(agent_result.get("warnings"))],
            record_id=email.record_id,
            received_at=email.received_at,
            processed_at=email.processed_at,
            mailbox=email.mailbox,
            uid=email.uid,
            message_id=email.message_id,
            pipeline_version=email.pipeline_version,
            processing_generation=email.processing_generation,
            original_email=original_email,
            agent_result=agent_result,
            attachments=[_attachment_response(record_id, item) for item in attachments],
            raw_download_url=f"/api/v1/emails/{record_id}/raw",
        )

    @app.get("/api/v1/emails/{record_id}/attachments/{attachment_id}/content")
    async def get_attachment(
        record_id: str, attachment_id: uuid.UUID, _: None = Depends(require_reader(selected, authentication_service))
    ) -> StreamingResponse:
        attachment = await result_repository.attachment(record_id, attachment_id)
        await asyncio.to_thread(object_storage.head, attachment.object_key)
        return StreamingResponse(
            object_storage.stream(attachment.object_key),
            media_type=attachment.detected_content_type,
            headers={
                "Content-Disposition": _safe_filename_header(attachment.safe_filename),
                "Content-Length": str(attachment.size),
            },
        )

    @app.get("/api/v1/emails/{record_id}/raw")
    async def get_raw(
        record_id: str, _: None = Depends(require_reader(selected, authentication_service))
    ) -> StreamingResponse:
        email, _attachments = await result_repository.detail(record_id)
        await asyncio.to_thread(object_storage.head, email.raw_key)
        return StreamingResponse(
            object_storage.stream(email.raw_key),
            media_type="message/rfc822",
            headers={
                "Content-Disposition": _safe_filename_header("message.eml"),
                "Content-Length": str(email.raw_size),
            },
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, log_level=get_settings().log_level.lower())
