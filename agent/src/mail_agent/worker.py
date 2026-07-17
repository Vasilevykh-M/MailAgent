"""Опрос полного очереди непрочитанных писем с корректной остановкой."""

from __future__ import annotations

import logging
import signal
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .graph.builder import MessageGraph
from .integrations.mail import MailGateway
from .logging import log_event
from .models import MessageReference
from .storage.processing_repository import ProcessingRepository, record_id

LOGGER = logging.getLogger(__name__)


class PollingWorker:
    def __init__(
        self,
        *,
        mail: MailGateway,
        graph: MessageGraph,
        repository: ProcessingRepository,
        work_dir: Path,
        mailbox: str,
        batch_size: int,
        poll_interval_seconds: int,
        max_concurrent_messages: int,
    ) -> None:
        self.mail, self.graph, self.repository = mail, graph, repository
        self.work_dir, self.mailbox, self.batch_size = work_dir, mailbox, batch_size
        self.poll_interval_seconds, self.max_concurrent_messages = poll_interval_seconds, max_concurrent_messages
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()
        log_event(LOGGER, "worker_stop_requested", component="worker", mailbox=self.mailbox)

    def _process(self, reference: MessageReference, *, force: bool = False) -> str:
        stable = record_id(reference.mailbox, reference.uid, reference.message_id)
        started = time.perf_counter()
        log_event(
            LOGGER,
            "message_processing_started",
            component="worker",
            record_id=stable,
            mailbox=reference.mailbox,
            uid=reference.uid,
        )
        existing = self.repository.get(stable)
        pipeline_version = getattr(
            self.graph, "pipeline_version", str(existing["pipeline_version"]) if existing else "worker"
        )
        self.repository.ensure(reference.mailbox, reference.uid, reference.message_id, pipeline_version)
        if not force and not self.repository.may_attempt(stable):
            log_event(
                LOGGER,
                "message_processing_deferred",
                component="worker",
                record_id=stable,
                mailbox=reference.mailbox,
                uid=reference.uid,
                status="deferred",
                duration_ms=round((time.perf_counter() - started) * 1000),
            )
            return "deferred"
        self.repository.current_record(stable)
        try:
            with tempfile.TemporaryDirectory(prefix="message-", dir=self.work_dir) as directory:
                result = self.graph.run(reference, Path(directory))
        finally:
            self.repository.current_record(None)
        status = str(result.get("status", "retryable_error"))
        log_event(
            LOGGER,
            "message_processed",
            component="worker",
            record_id=stable,
            mailbox=reference.mailbox,
            uid=reference.uid,
            status=status,
            failed_stage=str(result.get("failed_stage")) if result.get("failed_stage") else None,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        return status

    @staticmethod
    def _oldest_first(items: list[MessageReference]) -> list[MessageReference]:
        return sorted(items, key=lambda item: (item.date is None, item.date, int(item.uid)))

    def once(self) -> int:
        started = time.perf_counter()
        self.repository.poll_started()
        log_event(LOGGER, "mail_poll_started", component="worker", mailbox=self.mailbox)
        messages = self._oldest_first(self.mail.list_unread_all(self.mailbox, self.batch_size))
        if not messages:
            log_event(
                LOGGER,
                "mail_poll_completed",
                component="worker",
                mailbox=self.mailbox,
                message_count=0,
                duration_ms=round((time.perf_counter() - started) * 1000),
            )
            self.repository.poll_completed(0, 0)
            return 0
        processed_count = 0
        if self.max_concurrent_messages == 1:
            for reference in messages:
                if self.stop_event.is_set():
                    break
                try:
                    status = self._process(reference)
                    processed_count += status != "deferred"
                except Exception as exc:
                    processed_count += 1
                    log_event(
                        LOGGER,
                        "message_processing_failed",
                        level=logging.ERROR,
                        component="worker",
                        mailbox=reference.mailbox,
                        uid=reference.uid,
                        stage="worker",
                        error_type=type(exc).__name__,
                    )
                    stable = record_id(reference.mailbox, reference.uid, reference.message_id)
                    self.repository.error(stable, "worker", exc)
            log_event(
                LOGGER,
                "mail_poll_completed",
                component="worker",
                mailbox=self.mailbox,
                message_count=len(messages),
                processed_count=processed_count,
                duration_ms=round((time.perf_counter() - started) * 1000),
            )
            self.repository.poll_completed(len(messages), processed_count)
            return processed_count
        with ThreadPoolExecutor(max_workers=self.max_concurrent_messages, thread_name_prefix="mail-agent") as pool:
            futures = [pool.submit(self._process, reference) for reference in messages if not self.stop_event.is_set()]
            for future in futures:
                try:
                    status = future.result()
                    processed_count += status != "deferred"
                except Exception as exc:
                    processed_count += 1
                    log_event(
                        LOGGER,
                        "message_processing_failed",
                        level=logging.ERROR,
                        component="worker",
                        stage="worker",
                        error_type=type(exc).__name__,
                    )
        log_event(
            LOGGER,
            "mail_poll_completed",
            component="worker",
            mailbox=self.mailbox,
            message_count=len(messages),
            processed_count=processed_count,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        self.repository.poll_completed(len(messages), processed_count)
        return processed_count

    def process_uid(
        self, uid: str, mailbox: str | None = None, *, message_id: str | None = None, force: bool = False
    ) -> str:
        reference = MessageReference(uid=uid, mailbox=mailbox or self.mailbox, message_id=message_id)
        return self._process(reference, force=force)

    def run_forever(self) -> None:
        self.repository.worker_started()
        log_event(LOGGER, "worker_started", component="worker", mailbox=self.mailbox)
        try:
            while not self.stop_event.is_set():
                count = self.once()
                if count:
                    # Immediately recheck, including messages that appeared during processing.
                    continue
                self.stop_event.wait(self.poll_interval_seconds)
        finally:
            self.repository.worker_stopped()
            log_event(LOGGER, "worker_stopped", component="worker", mailbox=self.mailbox)

    def install_signal_handlers(self) -> None:
        def handler(_: int, __: object) -> None:
            self.stop()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
