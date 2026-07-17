from __future__ import annotations

from mail_agent.exceptions import PermanentError
from mail_agent.storage.processing_repository import record_id


def test_record_id_is_stable_and_table_commit_recovers(repository) -> None:
    first = record_id("INBOX", "12", "<id>")
    assert first == record_id("INBOX", "12", "<id>")
    repository.ensure("INBOX", "12", "<id>", "1")
    repository.start(first)
    repository.table_committed(first, {"remote_path": "/x.xlsx"})
    assert repository.get(first)["status"] == "table_committed"
    repository.completed(first)
    assert repository.get(first)["status"] == "completed"


def test_permanent_error_is_not_scheduled(repository) -> None:
    stable = repository.ensure("INBOX", "13", None, "1")
    repository.start(stable)
    assert repository.error(stable, "parse", PermanentError("bad file")) == "permanent_error"
    assert not repository.may_attempt(stable)


def test_manual_requeue_resets_a_permanent_error(repository) -> None:
    stable = repository.ensure("INBOX", "14", None, "1")
    repository.start(stable)
    repository.error(stable, "parse", PermanentError("bad file"))

    assert repository.requeue_failed(stable, include_permanent=True)
    item = repository.get(stable)
    assert item is not None
    assert item["status"] == "discovered"
    assert item["attempt_count"] == 0
    assert item["error_type"] is None
    assert repository.may_attempt(stable)


def test_manual_reprocess_resets_a_completed_record(repository) -> None:
    stable = repository.ensure("INBOX", "15", "<id>", "1")
    repository.start(stable)
    repository.table_committed(stable, {"remote_path": "/x.xlsx"})
    repository.completed(stable)

    assert repository.requeue_completed(stable)
    item = repository.get(stable)
    assert item is not None
    assert item["status"] == "discovered"
    assert item["table_commit_status"] == "pending"
    assert item["checkpoint"] is None
    assert item["completed_at"] is None
    assert repository.may_attempt(stable)


def test_start_clears_previous_manual_review_flag(repository) -> None:
    stable = repository.ensure("INBOX", "16", "<id>", "1")
    repository.start(stable)
    repository.mark_manual_review(stable, "summarize_message", "PermanentError")
    repository.completed(stable)
    assert repository.requeue_completed(stable)

    repository.start(stable)
    item = repository.get(stable)
    assert item is not None
    assert item["requires_manual_review"] == 0
    assert item["manual_review_stage"] is None
