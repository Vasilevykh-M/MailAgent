"""Транзакционное SQLite-хранилище idempotency, ошибок и кэша извлечений."""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import RetrySettings
from ..exceptions import PermanentError

STATUSES = {
    "discovered",
    "processing",
    "attachments_processed",
    "summarized",
    "table_committed",
    "completed",
    "retryable_error",
    "permanent_error",
}


def record_id(mailbox: str, uid: str, message_id: str | None) -> str:
    value = f"{mailbox}\0{uid}" + (f"\0{message_id}" if message_id else "")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ProcessingRepository:
    def __init__(self, path: Path, retries: RetrySettings) -> None:
        self.path, self.retries = path, retries
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS processing_records (
                  record_id TEXT PRIMARY KEY, mailbox TEXT NOT NULL, uid TEXT NOT NULL, message_id TEXT,
                  message_hash TEXT, status TEXT NOT NULL, attempt_count INTEGER NOT NULL DEFAULT 0,
                  last_attempt_at TEXT, next_retry_at TEXT, failed_stage TEXT, error_type TEXT, error_message TEXT,
                  attachment_hashes TEXT NOT NULL DEFAULT '[]', cached_extraction_results TEXT NOT NULL DEFAULT '{}',
                  checkpoint TEXT, pipeline_version TEXT NOT NULL, table_commit_status TEXT NOT NULL DEFAULT 'pending',
                  current_stage TEXT, sender TEXT, subject TEXT, message_date TEXT,
                  requires_manual_review INTEGER NOT NULL DEFAULT 0, manual_review_stage TEXT,
                  manual_review_error_type TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS processing_mail_uid ON processing_records(mailbox, uid, record_id);
                CREATE TABLE IF NOT EXISTS extraction_cache (
                  cache_key TEXT PRIMARY KEY, attachment_sha256 TEXT NOT NULL, pipeline_version TEXT NOT NULL,
                  parameters_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runtime_status (
                  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                  worker_state TEXT NOT NULL DEFAULT 'stopped', current_record_id TEXT,
                  last_poll_started_at TEXT, last_poll_completed_at TEXT,
                  last_poll_message_count INTEGER, last_poll_processed_count INTEGER,
                  updated_at TEXT NOT NULL
                );
                """
            )
            existing = {str(row["name"]) for row in connection.execute("PRAGMA table_info(processing_records)")}
            for name, definition in {
                "current_stage": "TEXT",
                "sender": "TEXT",
                "subject": "TEXT",
                "message_date": "TEXT",
                "requires_manual_review": "INTEGER NOT NULL DEFAULT 0",
                "manual_review_stage": "TEXT",
                "manual_review_error_type": "TEXT",
            }.items():
                if name not in existing:
                    connection.execute(f"ALTER TABLE processing_records ADD COLUMN {name} {definition}")
            connection.execute(
                "INSERT OR IGNORE INTO runtime_status(singleton, updated_at) VALUES (1, ?)", (self._now(),)
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def ensure(self, mailbox: str, uid: str, message_id: str | None, pipeline_version: str) -> str:
        stable = record_id(mailbox, uid, message_id)
        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO processing_records(record_id, mailbox, uid, message_id, status, pipeline_version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'discovered', ?, ?, ?) ON CONFLICT(record_id) DO NOTHING""",
                (stable, mailbox, uid, message_id, pipeline_version, now, now),
            )
            connection.execute("COMMIT")
        return stable

    def get(self, stable: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM processing_records WHERE record_id = ?", (stable,)).fetchone()
        return dict(row) if row else None

    def may_attempt(self, stable: str) -> bool:
        item = self.get(stable)
        if item is None:
            return True
        if item["status"] == "permanent_error" and not self.retries.permanent_error_retry:
            return False
        if item["status"] == "retryable_error" and item["next_retry_at"]:
            return datetime.fromisoformat(item["next_retry_at"]) <= datetime.now(UTC)
        return str(item["status"]) != "completed"

    def start(self, stable: str) -> None:
        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE processing_records
                   SET status='processing', current_stage='check_idempotency', attempt_count=attempt_count+1,
                       last_attempt_at=?, requires_manual_review=0, manual_review_stage=NULL,
                       manual_review_error_type=NULL, updated_at=? WHERE record_id=?""",
                (now, now, stable),
            )
            connection.execute("COMMIT")

    def stage(
        self,
        stable: str,
        status: str,
        *,
        checkpoint: dict[str, Any] | None = None,
        attachment_hashes: list[str] | None = None,
    ) -> None:
        if status not in STATUSES:
            raise ValueError("Unknown processing status")
        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET status=?, checkpoint=COALESCE(?, checkpoint), attachment_hashes=COALESCE(?, attachment_hashes),
                       updated_at=? WHERE record_id=?""",
                (
                    status,
                    json.dumps(checkpoint, ensure_ascii=False) if checkpoint is not None else None,
                    json.dumps(attachment_hashes) if attachment_hashes is not None else None,
                    self._now(),
                    stable,
                ),
            )

    def table_committed(self, stable: str, checkpoint: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET status='table_committed', table_commit_status='verified', checkpoint=?, updated_at=? WHERE record_id=?""",
                (json.dumps(checkpoint, ensure_ascii=False), self._now(), stable),
            )

    def completed(self, stable: str) -> None:
        now = self._now()
        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET status='completed', current_stage=NULL, completed_at=?, updated_at=? WHERE record_id=?""",
                (now, now, stable),
            )

    def mark_manual_review(self, stable: str, stage: str, error_type: str) -> None:
        """Сохраняет безопасную метку ручной проверки без текста письма или исключения."""

        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET requires_manual_review=1, manual_review_stage=?, manual_review_error_type=?, updated_at=?
                   WHERE record_id=?""",
                (stage, error_type, self._now(), stable),
            )

    def error(self, stable: str, stage: str, exc: Exception) -> str:
        item = self.get(stable) or {}
        attempts = int(item.get("attempt_count", 0))
        retryable = not isinstance(exc, PermanentError) and attempts < self.retries.max_attempts
        status = "retryable_error" if retryable else "permanent_error"
        next_retry: str | None = None
        if retryable:
            seconds = min(
                self.retries.max_backoff_seconds, self.retries.base_backoff_seconds * 2 ** max(0, attempts - 1)
            )
            seconds += random.uniform(0, min(5, seconds / 4))
            next_retry = (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()
        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET status=?, current_stage=NULL, failed_stage=?, error_type=?, error_message=?, next_retry_at=?, updated_at=?
                   WHERE record_id=?""",
                (status, stage, type(exc).__name__, str(exc)[:1000], next_retry, self._now(), stable),
            )
        return status

    def requeue_failed(self, stable: str, *, include_permanent: bool = False) -> bool:
        """Сбрасывает ошибку только по явной ручной команде оператора."""

        statuses = ("retryable_error", "permanent_error") if include_permanent else ("retryable_error",)
        placeholders = ",".join("?" for _ in statuses)
        with self._connection() as connection:
            cursor = connection.execute(
                f"""UPDATE processing_records
                    SET status='discovered', attempt_count=0, last_attempt_at=NULL, next_retry_at=NULL,
                        current_stage=NULL, failed_stage=NULL, error_type=NULL, error_message=NULL, updated_at=?
                    WHERE record_id=? AND status IN ({placeholders})""",
                (self._now(), stable, *statuses),
            )
        return cursor.rowcount == 1

    def requeue_completed(self, stable: str) -> bool:
        """Явно ставит готовое письмо в очередь для полного повторного анализа."""

        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE processing_records
                    SET status='discovered', attempt_count=0, last_attempt_at=NULL, next_retry_at=NULL,
                        current_stage=NULL, failed_stage=NULL, error_type=NULL, error_message=NULL,
                        checkpoint=NULL, table_commit_status='pending', completed_at=NULL,
                        requires_manual_review=0, manual_review_stage=NULL, manual_review_error_type=NULL,
                        updated_at=?
                    WHERE record_id=? AND status='completed'""",
                (self._now(), stable),
            )
        return cursor.rowcount == 1

    def retry_failed(self, *, include_permanent: bool = False) -> list[dict[str, Any]]:
        statuses = ("retryable_error", "permanent_error") if include_permanent else ("retryable_error",)
        placeholders = ",".join("?" for _ in statuses)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM processing_records WHERE status IN ({placeholders})", statuses
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _preview(value: object, limit: int) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = " ".join(value.split())
        return normalized[:limit] or None

    def message_fetched(self, stable: str, message: dict[str, Any]) -> None:
        """Сохраняет только короткие реквизиты для локальной панели, без тела и вложений."""

        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET sender=?, subject=?, message_date=?, updated_at=? WHERE record_id=?""",
                (
                    self._preview(message.get("from"), 320),
                    self._preview(message.get("subject"), 500),
                    self._preview(message.get("date"), 100),
                    self._now(),
                    stable,
                ),
            )

    def set_current_stage(self, stable: str, stage: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE processing_records SET current_stage=?, updated_at=? WHERE record_id=?",
                (stage, self._now(), stable),
            )

    def worker_started(self) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE runtime_status SET worker_state='running', updated_at=? WHERE singleton=1", (self._now(),)
            )

    def worker_stopped(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE runtime_status
                   SET worker_state='stopped', current_record_id=NULL, updated_at=? WHERE singleton=1""",
                (self._now(),),
            )

    def poll_started(self) -> None:
        now = self._now()
        with self._connection() as connection:
            connection.execute(
                """UPDATE runtime_status
                   SET worker_state='running', last_poll_started_at=?, updated_at=? WHERE singleton=1""",
                (now, now),
            )

    def poll_completed(self, message_count: int, processed_count: int) -> None:
        now = self._now()
        with self._connection() as connection:
            connection.execute(
                """UPDATE runtime_status
                   SET worker_state='waiting', last_poll_completed_at=?, last_poll_message_count=?,
                       last_poll_processed_count=?, current_record_id=NULL, updated_at=? WHERE singleton=1""",
                (now, message_count, processed_count, now),
            )

    def current_record(self, stable: str | None) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE runtime_status SET current_record_id=?, updated_at=? WHERE singleton=1",
                (stable, self._now()),
            )

    def find_by_uid(self, mailbox: str, uid: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM processing_records WHERE mailbox=? AND uid=? ORDER BY updated_at DESC", (mailbox, uid)
            ).fetchall()
        return [dict(row) for row in rows]

    def cache_get(self, attachment_sha256: str, pipeline_version: str, parameters_hash: str) -> dict[str, Any] | None:
        key = hashlib.sha256(f"{attachment_sha256}\0{pipeline_version}\0{parameters_hash}".encode()).hexdigest()
        with self._connection() as connection:
            row = connection.execute("SELECT result_json FROM extraction_cache WHERE cache_key=?", (key,)).fetchone()
        return json.loads(row["result_json"]) if row else None

    def cache_put(
        self, attachment_sha256: str, pipeline_version: str, parameters_hash: str, result: dict[str, Any]
    ) -> None:
        key = hashlib.sha256(f"{attachment_sha256}\0{pipeline_version}\0{parameters_hash}".encode()).hexdigest()
        with self._connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO extraction_cache VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    attachment_sha256,
                    pipeline_version,
                    parameters_hash,
                    json.dumps(result, ensure_ascii=False),
                    self._now(),
                ),
            )
