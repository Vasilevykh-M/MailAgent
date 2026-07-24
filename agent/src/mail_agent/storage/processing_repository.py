"""Транзакционное SQLite-хранилище состояния писем и журнала узлов графа."""

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
    "result_committed",
    "completed",
    "retryable_error",
    "permanent_error",
}
NODE_STATUSES = {"queued", "running", "completed", "retryable_error", "permanent_error", "invalidated"}


def record_id(mailbox: str, uid: str, message_id: str | None) -> str:
    value = f"{mailbox}\0{uid}" + (f"\0{message_id}" if message_id else "")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ProcessingRepository:
    """Общее состояние письма и durable-журнал выполнения отдельных узлов."""

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
                  checkpoint TEXT, pipeline_version TEXT NOT NULL, processing_generation INTEGER NOT NULL DEFAULT 0,
                  api_commit_status TEXT NOT NULL DEFAULT 'pending', current_stage TEXT, sender TEXT, subject TEXT,
                  message_date TEXT, requires_manual_review INTEGER NOT NULL DEFAULT 0, manual_review_stage TEXT,
                  manual_review_error_type TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS processing_mail_uid ON processing_records(mailbox, uid, record_id);
                CREATE TABLE IF NOT EXISTS extraction_cache (
                  cache_key TEXT PRIMARY KEY, attachment_sha256 TEXT NOT NULL, pipeline_version TEXT NOT NULL,
                  parameters_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS node_executions (
                  execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  record_id TEXT NOT NULL, thread_id TEXT NOT NULL, node_name TEXT NOT NULL,
                  pipeline_version TEXT NOT NULL, execution_key TEXT NOT NULL,
                  input_context_hash TEXT NOT NULL, status TEXT NOT NULL,
                  attempt_count INTEGER NOT NULL DEFAULT 0, previous_status TEXT,
                  context_json TEXT NOT NULL, output_json TEXT, error_type TEXT, error_message TEXT,
                  created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT, updated_at TEXT NOT NULL,
                  UNIQUE(record_id, node_name, pipeline_version, execution_key)
                );
                CREATE INDEX IF NOT EXISTS node_executions_record_stage
                  ON node_executions(record_id, node_name, updated_at DESC);
                CREATE INDEX IF NOT EXISTS node_executions_record_status
                  ON node_executions(record_id, status, updated_at DESC);
                CREATE TABLE IF NOT EXISTS node_execution_attempts (
                  execution_id INTEGER NOT NULL, attempt_number INTEGER NOT NULL, status TEXT NOT NULL,
                  error_type TEXT, created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT, updated_at TEXT NOT NULL,
                  PRIMARY KEY(execution_id, attempt_number),
                  FOREIGN KEY(execution_id) REFERENCES node_executions(execution_id)
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
                "processing_generation": "INTEGER NOT NULL DEFAULT 0",
                "api_commit_status": "TEXT NOT NULL DEFAULT 'pending'",
            }.items():
                if name not in existing:
                    connection.execute(f"ALTER TABLE processing_records ADD COLUMN {name} {definition}")
            # Старый `table_committed` доказывает лишь Excel-запись, а не commit Results API.
            # Поэтому он безопасно возвращается в очередь и не может привести к установке `\\Seen`.
            connection.execute(
                """UPDATE processing_records
                   SET status='discovered', api_commit_status='legacy_unmigrated', checkpoint=NULL, current_stage=NULL,
                       updated_at=?
                   WHERE status='table_committed'""",
                (self._now(),),
            )
            connection.execute(
                "INSERT OR IGNORE INTO runtime_status(singleton, updated_at) VALUES (1, ?)", (self._now(),)
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _row_execution(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        output = item.pop("output_json", None)
        context = item.pop("context_json", None)
        item["output"] = json.loads(output) if isinstance(output, str) else None
        item["context"] = json.loads(context) if isinstance(context, str) else None
        return item

    def ensure(self, mailbox: str, uid: str, message_id: str | None, pipeline_version: str) -> str:
        """Создаёт запись либо безопасно начинает новый run при смене версии pipeline."""

        stable = record_id(mailbox, uid, message_id)
        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT pipeline_version FROM processing_records WHERE record_id=?", (stable,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """INSERT INTO processing_records(
                           record_id, mailbox, uid, message_id, status, pipeline_version, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, 'discovered', ?, ?, ?)""",
                    (stable, mailbox, uid, message_id, pipeline_version, now, now),
                )
            elif str(existing["pipeline_version"]) != pipeline_version:
                connection.execute(
                    """UPDATE processing_records
                       SET pipeline_version=?, processing_generation=processing_generation+1, status='discovered',
                           next_retry_at=NULL, current_stage=NULL, failed_stage=NULL, error_type=NULL,
                           error_message=NULL, checkpoint=NULL, api_commit_status='pending', completed_at=NULL,
                           requires_manual_review=0, manual_review_stage=NULL, manual_review_error_type=NULL,
                           updated_at=? WHERE record_id=?""",
                    (pipeline_version, now, stable),
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
            return datetime.fromisoformat(str(item["next_retry_at"])) <= datetime.now(UTC)
        return str(item["status"]) != "completed"

    def start(self, stable: str) -> None:
        """Фиксирует новую попытку всего письма, не удаляя журнал успешных узлов."""

        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE processing_records
                   SET status='processing', current_stage='check_idempotency', attempt_count=attempt_count+1,
                       last_attempt_at=?, next_retry_at=NULL, requires_manual_review=0, manual_review_stage=NULL,
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
        """Совместимый API для краткого статуса, без хранения полного graph state."""

        if status not in STATUSES:
            raise ValueError("Unknown processing status")
        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET status=?, checkpoint=COALESCE(?, checkpoint), attachment_hashes=COALESCE(?, attachment_hashes),
                       updated_at=? WHERE record_id=?""",
                (
                    status,
                    self._json(checkpoint) if checkpoint is not None else None,
                    self._json(attachment_hashes) if attachment_hashes is not None else None,
                    self._now(),
                    stable,
                ),
            )

    def result_committed(self, stable: str, checkpoint: dict[str, Any]) -> None:
        """Фиксирует подтверждённый Results API commit; полный state остаётся в LangGraph."""

        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET status='result_committed', api_commit_status='committed', checkpoint=?, updated_at=? WHERE record_id=?""",
                (self._json(checkpoint), self._now(), stable),
            )

    def table_committed(self, stable: str, checkpoint: dict[str, Any]) -> None:
        """Совместимость со старым API: Excel commit не является результатом API и не завершает письмо."""

        with self._connection() as connection:
            connection.execute(
                """UPDATE processing_records
                   SET status='discovered', api_commit_status='legacy_unmigrated', checkpoint=?, updated_at=?
                   WHERE record_id=?""",
                (self._json(checkpoint), self._now(), stable),
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
                (stage, error_type[:160], self._now(), stable),
            )

    def _error(self, stable: str, stage: str, error_type: str, permanent: bool) -> str:
        item = self.get(stable) or {}
        attempts = int(item.get("attempt_count", 0))
        retryable = not permanent and attempts < self.retries.max_attempts
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
                   SET status=?, current_stage=NULL, failed_stage=?, error_type=?,
                       error_message='Детали ошибки не сохраняются.', next_retry_at=?, updated_at=?
                   WHERE record_id=?""",
                (status, stage, error_type[:160], next_retry, self._now(), stable),
            )
        return status

    def error(self, stable: str, stage: str, exc: Exception) -> str:
        return self._error(stable, stage, type(exc).__name__, isinstance(exc, PermanentError))

    def error_safe(self, stable: str, stage: str, error_type: str, *, permanent: bool) -> str:
        return self._error(stable, stage, error_type, permanent)

    def requeue_failed(self, stable: str, *, include_permanent: bool = False) -> bool:
        """Ставит ошибку в очередь, сохраняя счётчики и результаты успешных узлов."""

        statuses = ("retryable_error", "permanent_error") if include_permanent else ("retryable_error",)
        placeholders = ",".join("?" for _ in statuses)
        with self._connection() as connection:
            cursor = connection.execute(
                f"""UPDATE processing_records
                    SET status='discovered', next_retry_at=NULL, current_stage=NULL, failed_stage=NULL,
                        error_type=NULL, error_message=NULL, updated_at=?
                    WHERE record_id=? AND status IN ({placeholders})""",
                (self._now(), stable, *statuses),
            )
        return cursor.rowcount == 1

    def requeue_for_reprocess(self, stable: str) -> bool:
        """Инвалидирует все cached результаты конкретного письма для полного --reprocess."""

        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """UPDATE processing_records
                   SET status='discovered', processing_generation=processing_generation+1, next_retry_at=NULL,
                       current_stage=NULL, failed_stage=NULL, error_type=NULL, error_message=NULL, checkpoint=NULL,
                       api_commit_status='pending', completed_at=NULL, requires_manual_review=0,
                       manual_review_stage=NULL, manual_review_error_type=NULL, updated_at=?
                   WHERE record_id=?""",
                (now, stable),
            )
            if cursor.rowcount == 1:
                connection.execute(
                    """UPDATE node_executions SET previous_status=status, status='invalidated', updated_at=?
                       WHERE record_id=? AND status != 'invalidated'""",
                    (now, stable),
                )
            connection.execute("COMMIT")
        return cursor.rowcount == 1

    def requeue_completed(self, stable: str) -> bool:
        """Совместимое имя операции полного повторного анализа."""

        item = self.get(stable)
        return bool(item and item["status"] == "completed" and self.requeue_for_reprocess(stable))

    def retry_failed(self, *, include_permanent: bool = False) -> list[dict[str, Any]]:
        statuses = ("retryable_error", "permanent_error") if include_permanent else ("retryable_error",)
        placeholders = ",".join("?" for _ in statuses)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM processing_records WHERE status IN ({placeholders})", statuses
            ).fetchall()
        return [dict(row) for row in rows]

    def claim_node_execution(
        self,
        *,
        record: str,
        thread_id: str,
        node_name: str,
        pipeline_version: str,
        execution_key: str,
        input_context_hash: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Атомарно получает право выполнить узел либо возвращает его durable результат."""

        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM node_executions
                   WHERE record_id=? AND node_name=? AND pipeline_version=? AND execution_key=?""",
                (record, node_name, pipeline_version, execution_key),
            ).fetchone()
            if row is not None and row["status"] == "completed" and row["output_json"]:
                connection.execute("COMMIT")
                return {"decision": "reuse", "execution": self._row_execution(row)}
            if row is not None and row["status"] == "running":
                connection.execute("COMMIT")
                return {"decision": "busy", "execution": self._row_execution(row)}
            previous_status = str(row["status"]) if row is not None else None
            if row is None:
                cursor = connection.execute(
                    """INSERT INTO node_executions(
                           record_id, thread_id, node_name, pipeline_version, execution_key, input_context_hash,
                           status, context_json, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)""",
                    (
                        record,
                        thread_id,
                        node_name,
                        pipeline_version,
                        execution_key,
                        input_context_hash,
                        self._json(context),
                        now,
                        now,
                    ),
                )
                if cursor.lastrowid is None:  # pragma: no cover - SQLite INSERT invariant
                    connection.execute("ROLLBACK")
                    raise RuntimeError("SQLite не вернул идентификатор выполнения узла.")
                execution_id = int(cursor.lastrowid)
                attempt = 1
                connection.execute(
                    """UPDATE node_executions
                       SET status='running', attempt_count=1, started_at=?, updated_at=? WHERE execution_id=?""",
                    (now, now, execution_id),
                )
            else:
                execution_id = int(row["execution_id"])
                attempt = int(row["attempt_count"]) + 1
                connection.execute(
                    """UPDATE node_executions
                       SET status='running', attempt_count=?, previous_status=?, context_json=?, output_json=NULL,
                           error_type=NULL, error_message=NULL, started_at=?, completed_at=NULL, updated_at=?
                       WHERE execution_id=?""",
                    (attempt, previous_status, self._json(context), now, now, execution_id),
                )
            connection.execute(
                """INSERT INTO node_execution_attempts(
                       execution_id, attempt_number, status, created_at, started_at, updated_at
                   ) VALUES (?, ?, 'running', ?, ?, ?)""",
                (execution_id, attempt, now, now, now),
            )
            claimed = connection.execute(
                "SELECT * FROM node_executions WHERE execution_id=?", (execution_id,)
            ).fetchone()
            connection.execute("COMMIT")
        if claimed is None:  # pragma: no cover - SQLite invariant
            raise RuntimeError("Не удалось получить запись выполнения узла.")
        return {"decision": "execute", "execution": self._row_execution(claimed)}

    def store_node_result(self, execution_key: str, output: dict[str, Any]) -> None:
        """Сохраняет JSON patch до checkpoint; статус остаётся running до подтверждения graph."""

        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE node_executions SET output_json=?, updated_at=?
                   WHERE execution_key=? AND status='running'""",
                (self._json(output), self._now(), execution_key),
            )
        if cursor.rowcount != 1:
            raise RuntimeError("Результат узла нельзя сохранить без активного выполнения.")

    def complete_node_execution(self, execution_key: str) -> None:
        """Помечает узел completed только после checkpoint, созданного предыдущим superstep."""

        now = self._now()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT execution_id, attempt_count, output_json FROM node_executions WHERE execution_key=?",
                (execution_key,),
            ).fetchone()
            if row is None or not row["output_json"]:
                connection.execute("ROLLBACK")
                raise RuntimeError("Checkpoint подтверждает отсутствующий результат узла.")
            if row["output_json"] and row["execution_id"] and row["attempt_count"]:
                connection.execute(
                    """UPDATE node_executions
                       SET status='completed', error_type=NULL, error_message=NULL, completed_at=?, updated_at=?
                       WHERE execution_id=? AND status IN ('running', 'retryable_error') AND output_json IS NOT NULL""",
                    (now, now, row["execution_id"]),
                )
                connection.execute(
                    """UPDATE node_execution_attempts
                       SET status='completed', error_type=NULL, completed_at=?, updated_at=?
                       WHERE execution_id=? AND attempt_number=? AND status IN ('running', 'retryable_error')""",
                    (now, now, row["execution_id"], row["attempt_count"]),
                )
            connection.execute("COMMIT")

    def fail_node_execution(self, execution_key: str, error_type: str, *, permanent: bool) -> None:
        """Сохраняет только безопасную классификацию ошибки, без её текста и пользовательских данных."""

        now = self._now()
        status = "permanent_error" if permanent else "retryable_error"
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT execution_id, attempt_count FROM node_executions WHERE execution_key=?", (execution_key,)
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                raise RuntimeError("Ошибка относится к неизвестному выполнению узла.")
            connection.execute(
                """UPDATE node_executions
                   SET status=?, error_type=?, error_message='Детали ошибки не сохраняются.', completed_at=?, updated_at=?
                   WHERE execution_id=?""",
                (status, error_type[:160], now, now, row["execution_id"]),
            )
            connection.execute(
                """UPDATE node_execution_attempts SET status=?, error_type=?, completed_at=?, updated_at=?
                   WHERE execution_id=? AND attempt_number=?""",
                (status, error_type[:160], now, now, row["execution_id"], row["attempt_count"]),
            )
            connection.execute("COMMIT")

    def recover_abandoned_node_executions(self) -> int:
        """Освобождает узлы, оставшиеся ``running`` после остановки процесса.

        Вызывать только после захвата ``CoreWorkerLock``: иначе живой worker мог бы
        продолжать выполнение того же узла. Сохранённый output не удаляется — если
        action уже попал в checkpoint, технический finalize-узел подтвердит его.
        """

        now = self._now()
        error_type = "AbandonedNodeExecution"
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT execution_id, attempt_count FROM node_executions WHERE status='running'"
            ).fetchall()
            if not rows:
                connection.execute("COMMIT")
                return 0
            execution_ids = [int(row["execution_id"]) for row in rows]
            placeholders = ",".join("?" for _ in execution_ids)
            connection.execute(
                f"""UPDATE node_executions
                    SET previous_status=status, status='retryable_error', error_type=?,
                        error_message='Детали ошибки не сохраняются.', completed_at=?, updated_at=?
                    WHERE execution_id IN ({placeholders}) AND status='running'""",
                (error_type, now, now, *execution_ids),
            )
            for row in rows:
                connection.execute(
                    """UPDATE node_execution_attempts
                       SET status='retryable_error', error_type=?, completed_at=?, updated_at=?
                       WHERE execution_id=? AND attempt_number=? AND status='running'""",
                    (error_type, now, now, int(row["execution_id"]), int(row["attempt_count"])),
                )
            connection.execute("COMMIT")
        return len(rows)

    def invalidate_node_execution(self, execution_key: str) -> None:
        """Отменяет reuse результата, который зависит от уже удалённых временных файлов."""

        with self._connection() as connection:
            connection.execute(
                """UPDATE node_executions SET previous_status=status, status='invalidated', updated_at=?
                   WHERE execution_key=? AND status='completed'""",
                (self._now(), execution_key),
            )

    def get_node_execution(
        self, record: str, node_name: str, *, execution_key: str | None = None
    ) -> dict[str, Any] | None:
        query = "SELECT * FROM node_executions WHERE record_id=? AND node_name=?"
        params: list[str] = [record, node_name]
        if execution_key is not None:
            query += " AND execution_key=?"
            params.append(execution_key)
        query += " ORDER BY updated_at DESC LIMIT 1"
        with self._connection() as connection:
            row = connection.execute(query, params).fetchone()
        return self._row_execution(row) if row else None

    def node_attempt_history(self, execution_key: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT attempts.* FROM node_execution_attempts AS attempts
                   JOIN node_executions AS executions ON executions.execution_id=attempts.execution_id
                   WHERE executions.execution_key=? ORDER BY attempts.attempt_number""",
                (execution_key,),
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
                (key, attachment_sha256, pipeline_version, parameters_hash, self._json(result), self._now()),
            )
