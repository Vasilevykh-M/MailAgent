"""PostgreSQL-модели и репозиторий с bounded запросами к monthly partitions."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, and_, delete, func, select, text, tuple_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import Settings
from .errors import ConflictError, NotFoundError
from .schemas import EmailListItem, IngestionPayload
from .storage.s3 import StoredObject


class Base(DeclarativeBase):
    pass


class EmailLocator(Base):
    __tablename__ = "email_locator"

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = {"postgresql_partition_by": "RANGE (received_at)"}

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mailbox: Mapped[str] = mapped_column(String(512), nullable=False)
    uid: Mapped[str] = mapped_column(String(512), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(2048))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    sender: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    original_email: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    agent_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    raw_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_key: Mapped[str] = mapped_column(Text, nullable=False)
    raw_etag: Mapped[str | None] = mapped_column(String(512))
    raw_version_id: Mapped[str | None] = mapped_column(String(1024))
    raw_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Attachment(Base):
    __tablename__ = "email_attachments"
    __table_args__ = {"postgresql_partition_by": "RANGE (received_at)"}

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    attachment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_inline: Mapped[bool] = mapped_column(nullable=False)
    content_id: Mapped[str | None] = mapped_column(String(1024))
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    etag: Mapped[str | None] = mapped_column(String(512))
    version_id: Mapped[str | None] = mapped_column(String(1024))
    processing_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class AttachmentObject:
    position: int
    metadata: dict[str, Any]
    storage: StoredObject
    processing_result: dict[str, Any] | None


@dataclass(frozen=True)
class CommitResult:
    committed_at: datetime
    idempotent: bool


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self) -> None:
        await self.engine.dispose()

    async def ready(self) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            return False
        return True


def _month_bounds(moment: datetime) -> tuple[datetime, datetime]:
    value = moment.astimezone(UTC)
    start = value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


class ResultRepository:
    """Все чтения heavy tables ограничены одной календарной партицией."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def commit(
        self,
        payload: IngestionPayload,
        raw: StoredObject,
        attachments: Sequence[AttachmentObject],
    ) -> CommitResult:
        now, fingerprint = datetime.now(UTC), payload.fingerprint()
        async with self.database.sessions() as session, session.begin():
            locator = await session.get(EmailLocator, payload.record_id, with_for_update=True)
            if locator is not None:
                if payload.processing_generation < locator.processing_generation:
                    raise ConflictError("Older processing generation")
                if payload.processing_generation == locator.processing_generation:
                    if locator.payload_fingerprint != fingerprint:
                        raise ConflictError("Different payload for same processing generation")
                    return CommitResult(locator.updated_at, idempotent=True)
                if locator.received_at != payload.received_at:
                    raise ConflictError("received_at is immutable for record_id")
                locator.processing_generation = payload.processing_generation
                locator.schema_version = payload.schema_version
                locator.payload_fingerprint = fingerprint
                locator.updated_at = now
            else:
                session.add(
                    EmailLocator(
                        record_id=payload.record_id,
                        received_at=payload.received_at,
                        processing_generation=payload.processing_generation,
                        schema_version=payload.schema_version,
                        payload_fingerprint=fingerprint,
                        created_at=now,
                        updated_at=now,
                    )
                )
            received_at = payload.received_at
            email = await session.get(Email, {"received_at": received_at, "record_id": payload.record_id})
            values = payload.original_email.model_dump(mode="json", by_alias=True)
            if email is None:
                session.add(
                    Email(
                        received_at=received_at,
                        record_id=payload.record_id,
                        mailbox=payload.mailbox,
                        uid=payload.uid,
                        message_id=payload.message_id,
                        processed_at=payload.processed_at,
                        pipeline_version=payload.pipeline_version,
                        schema_version=payload.schema_version,
                        processing_generation=payload.processing_generation,
                        sender=payload.original_email.sender,
                        subject=payload.original_email.subject,
                        original_email=values,
                        agent_result=payload.agent_result,
                        raw_bucket=raw.bucket,
                        raw_key=raw.key,
                        raw_etag=raw.etag,
                        raw_version_id=raw.version_id,
                        raw_size=raw.size,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                for key, value in {
                    "mailbox": payload.mailbox,
                    "uid": payload.uid,
                    "message_id": payload.message_id,
                    "processed_at": payload.processed_at,
                    "pipeline_version": payload.pipeline_version,
                    "schema_version": payload.schema_version,
                    "processing_generation": payload.processing_generation,
                    "sender": payload.original_email.sender,
                    "subject": payload.original_email.subject,
                    "original_email": values,
                    "agent_result": payload.agent_result,
                    "raw_bucket": raw.bucket,
                    "raw_key": raw.key,
                    "raw_etag": raw.etag,
                    "raw_version_id": raw.version_id,
                    "raw_size": raw.size,
                    "updated_at": now,
                }.items():
                    setattr(email, key, value)
                await session.execute(
                    delete(Attachment).where(
                        Attachment.received_at == received_at, Attachment.record_id == payload.record_id
                    )
                )
            for item in attachments:
                metadata = item.metadata
                session.add(
                    Attachment(
                        received_at=received_at,
                        record_id=payload.record_id,
                        position=item.position,
                        original_filename=str(metadata["original_filename"]),
                        safe_filename=str(metadata["safe_filename"]),
                        content_type=str(metadata["content_type"]),
                        detected_content_type=str(metadata["detected_content_type"]),
                        size=int(metadata["size"]),
                        sha256=str(metadata["sha256"]),
                        is_inline=bool(metadata["is_inline"]),
                        content_id=metadata.get("content_id"),
                        bucket=item.storage.bucket,
                        object_key=item.storage.key,
                        etag=item.storage.etag,
                        version_id=item.storage.version_id,
                        processing_result=item.processing_result,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return CommitResult(now, idempotent=False)

    async def detail(self, record_id: str) -> tuple[Email, list[Attachment]]:
        async with self.database.sessions() as session:
            locator = await session.get(EmailLocator, record_id)
            if locator is None:
                raise NotFoundError()
            start, end = _month_bounds(locator.received_at)
            email = (
                await session.execute(
                    select(Email).where(
                        Email.record_id == record_id, Email.received_at >= start, Email.received_at < end
                    )
                )
            ).scalar_one_or_none()
            if email is None:
                raise NotFoundError()
            attachments = list(
                (
                    await session.execute(
                        select(Attachment)
                        .where(
                            Attachment.record_id == record_id,
                            Attachment.received_at >= start,
                            Attachment.received_at < end,
                        )
                        .order_by(Attachment.position)
                    )
                ).scalars()
            )
        return email, attachments

    async def attachment(self, record_id: str, attachment_id: uuid.UUID) -> Attachment:
        async with self.database.sessions() as session:
            locator = await session.get(EmailLocator, record_id)
            if locator is None:
                raise NotFoundError()
            start, end = _month_bounds(locator.received_at)
            attachment = (
                await session.execute(
                    select(Attachment).where(
                        Attachment.attachment_id == attachment_id,
                        Attachment.record_id == record_id,
                        Attachment.received_at >= start,
                        Attachment.received_at < end,
                    )
                )
            ).scalar_one_or_none()
        if attachment is None:
            raise NotFoundError()
        return attachment

    async def list_month(
        self,
        month: datetime,
        *,
        limit: int,
        cursor: tuple[datetime, str] | None,
        mailbox: str | None = None,
    ) -> list[EmailListItem]:
        start, end = _month_bounds(month)
        conditions = [Email.received_at >= start, Email.received_at < end]
        if cursor is not None and start <= cursor[0] < end:
            conditions.append(tuple_(Email.received_at, Email.record_id) < cursor)
        if mailbox:
            conditions.append(Email.mailbox == mailbox)
        async with self.database.sessions() as session:
            rows = list(
                (
                    await session.execute(
                        select(Email)
                        .where(and_(*conditions))
                        .order_by(Email.received_at.desc(), Email.record_id.desc())
                        .limit(limit)
                    )
                ).scalars()
            )
        return [
            EmailListItem(
                record_id=row.record_id,
                received_at=row.received_at,
                **{"from": row.sender},
                subject=row.subject,
                summary_preview=str(row.agent_result.get("summary", {}).get("summary_ru", ""))[:500],
                attachment_count=int(row.agent_result.get("attachment_count", 0)),
                confidence=row.agent_result.get("summary", {}).get("confidence"),
            )
            for row in rows
        ]

    async def statistics(self, start: datetime, end: datetime, *, mailbox: str | None = None) -> dict[str, Any]:
        """Возвращает агрегаты периода, не делая неограниченного сканирования партиций."""

        total_emails = 0
        total_attachments = 0
        classifications: dict[tuple[str | None, str | None, str | None], int] = {}
        month = _month_bounds(start)[0]
        async with self.database.sessions() as session:
            # Лимит периода проверяется router; каждая итерация ограничена одной monthly partition.
            while month < end:
                month_end = _month_bounds(month)[1]
                window_start, window_end = max(start, month), min(end, month_end)
                email_conditions = [Email.received_at >= window_start, Email.received_at < window_end]
                attachment_conditions = [Attachment.received_at >= window_start, Attachment.received_at < window_end]
                if mailbox:
                    email_conditions.append(Email.mailbox == mailbox)
                    attachment_conditions.append(
                        Attachment.record_id.in_(select(Email.record_id).where(and_(*email_conditions)))
                    )

                total_emails += int(
                    (
                        await session.execute(select(func.count(Email.record_id)).where(and_(*email_conditions)))
                    ).scalar_one()
                )
                total_attachments += int(
                    (
                        await session.execute(
                            select(func.count(Attachment.attachment_id)).where(and_(*attachment_conditions))
                        )
                    ).scalar_one()
                )

                classification = Email.agent_result["summary"]["classification"]
                status = classification["status"].astext
                class_code = classification["class_code"].astext
                class_name_ru = classification["class_name_ru"].astext
                rows = await session.execute(
                    select(status, class_code, class_name_ru, func.count(Email.record_id))
                    .where(and_(*email_conditions))
                    .group_by(status, class_code, class_name_ru)
                )
                for item_status, item_code, item_name, count in rows:
                    key = (
                        str(item_status) if item_status is not None else None,
                        str(item_code) if item_code is not None else None,
                        str(item_name) if item_name is not None else None,
                    )
                    classifications[key] = classifications.get(key, 0) + int(count)
                month = month_end

        return {
            "total_emails": total_emails,
            "total_attachments": total_attachments,
            "classifications": [
                {
                    "status": status,
                    "class_code": class_code,
                    "class_name_ru": class_name_ru,
                    "count": count,
                }
                for (status, class_code, class_name_ru), count in sorted(
                    classifications.items(),
                    key=lambda item: (-item[1], item[0][1] or "", item[0][0] or ""),
                )
            ],
        }
