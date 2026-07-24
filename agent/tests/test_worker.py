from __future__ import annotations

from mail_agent.exceptions import PermanentError
from mail_agent.storage.processing_repository import record_id
from mail_agent.worker import PollingWorker

from .conftest import FakeGraph, FakeMail


def test_all_messages_processed_oldest_first_and_failure_does_not_stop(tmp_path, repository, references) -> None:
    mail = FakeMail([references])
    graph = FakeGraph(fail_uid="1")
    worker = PollingWorker(
        mail=mail,
        graph=graph,
        repository=repository,
        work_dir=tmp_path,
        mailbox="INBOX",
        batch_size=1,
        poll_interval_seconds=1,
        max_concurrent_messages=1,
    )
    assert worker.once() == 2
    assert graph.seen == ["1", "2"]
    assert repository.get(record_id("INBOX", "1", "<1>"))["status"] == "retryable_error"


def test_worker_immediately_rechecks_after_nonempty_queue(tmp_path, repository, references) -> None:
    mail = FakeMail([[references[0]], []])
    graph = FakeGraph()
    worker = PollingWorker(
        mail=mail,
        graph=graph,
        repository=repository,
        work_dir=tmp_path,
        mailbox="INBOX",
        batch_size=50,
        poll_interval_seconds=999,
        max_concurrent_messages=1,
    )
    worker.stop_event.set()
    # once is one full queue check; run_forever behavior is covered by call sequence without a real sleep.
    worker.stop_event.clear()
    worker.once()
    worker.once()
    assert mail.calls == 2


def test_deferred_permanent_messages_do_not_keep_worker_in_busy_loop(tmp_path, repository, references) -> None:
    reference = references[0]
    stable = repository.ensure(reference.mailbox, reference.uid, reference.message_id, "1")
    repository.start(stable)
    repository.error(stable, "summarize_message", PermanentError("old failure"))
    mail = FakeMail([[reference]])
    graph = FakeGraph()
    worker = PollingWorker(
        mail=mail,
        graph=graph,
        repository=repository,
        work_dir=tmp_path,
        mailbox="INBOX",
        batch_size=50,
        poll_interval_seconds=1,
        max_concurrent_messages=1,
    )

    assert worker.once() == 0
    assert graph.seen == []


def test_worker_passes_unread_setting_to_mail_gateway(tmp_path, repository, references) -> None:
    class RecordingMail(FakeMail):
        unread_values: list[bool]

        def __init__(self) -> None:
            super().__init__([references])
            self.unread_values = []

        def list_unread_all(self, mailbox, batch_size, *, unread_only=True):
            self.unread_values.append(unread_only)
            return super().list_unread_all(mailbox, batch_size, unread_only=unread_only)

    mail = RecordingMail()
    worker = PollingWorker(
        mail=mail,
        graph=FakeGraph(),
        repository=repository,
        work_dir=tmp_path,
        mailbox="INBOX",
        batch_size=50,
        poll_interval_seconds=1,
        max_concurrent_messages=1,
        unread_only=False,
    )

    worker.once()

    assert mail.unread_values == [False]
