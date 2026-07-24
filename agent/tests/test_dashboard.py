from __future__ import annotations

import json
from pathlib import Path

from mail_agent.config import RetrySettings
from mail_agent.dashboard import _HTML, DashboardStore
from mail_agent.storage.processing_repository import ProcessingRepository


def test_dashboard_snapshot_shows_progress_without_message_body(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    repository = ProcessingRepository(db_path, RetrySettings())
    stable = repository.ensure("INBOX", "42", "<42@example.test>", "1")
    repository.start(stable)
    repository.message_fetched(
        stable,
        {
            "from": "sender@example.test",
            "subject": "Тема письма",
            "date": "2026-07-12T14:00:00+00:00",
            "text_plain": "Содержимое письма не должно попасть в панель.",
        },
    )
    repository.set_current_stage(stable, "summarize_message")
    repository.worker_started()
    repository.poll_started()
    repository.current_record(stable)

    snapshot = DashboardStore(db_path, queue_limit=10, recent_limit=10).snapshot()

    assert snapshot["runtime"]["worker_state"] == "running"
    assert snapshot["current"]["current_stage"] == "summarize_message"
    assert snapshot["current"]["subject"] == "Тема письма"
    assert snapshot["queue"][0]["sender"] == "sender@example.test"
    assert "Содержимое письма" not in json.dumps(snapshot, ensure_ascii=False)


def test_dashboard_translates_statuses_and_stages_to_russian() -> None:
    assert "processing:'Обрабатывается'" in _HTML
    assert "retryable_error:'Повтор будет выполнен'" in _HTML
    assert "manual_review:'Требуется ручная проверка'" in _HTML
    assert "summarize_message:'Суммаризация письма'" in _HTML
    assert "AttachmentProcessingUnavailable:'Не удалось корректно обработать одно или несколько вложений'" in _HTML
    assert "NodeExecutionBusy:'Узел уже выполняется; задача будет повторена'" in _HTML
    assert "AbandonedNodeExecution:'Предыдущее выполнение узла было прервано; задача будет повторена'" in _HTML


def test_dashboard_keeps_completed_manual_review_in_attention_queue(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    repository = ProcessingRepository(db_path, RetrySettings())
    stable = repository.ensure("INBOX", "43", "<43@example.test>", "1")
    repository.start(stable)
    repository.mark_manual_review(stable, "summarize_message", "LLMResponseFormatError")
    repository.completed(stable)

    snapshot = DashboardStore(db_path, queue_limit=10, recent_limit=10).snapshot()

    assert snapshot["queue"][0]["status"] == "completed"
    assert snapshot["queue"][0]["requires_manual_review"]
    assert snapshot["queue"][0]["manual_review_stage"] == "summarize_message"


def test_dashboard_tracks_all_parallel_active_records(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    repository = ProcessingRepository(db_path, RetrySettings())
    first = repository.ensure("INBOX", "1", "<1>", "1")
    second = repository.ensure("INBOX", "2", "<2>", "1")
    repository.start(first)
    repository.start(second)
    repository.worker_started()
    repository.poll_started()
    repository.current_record(first)
    repository.current_record(second)
    repository.current_record(None, expected=second)

    snapshot = DashboardStore(db_path, queue_limit=10, recent_limit=10).snapshot()

    assert snapshot["runtime"]["active_record_count"] == 1
    assert [item["record_id"] for item in snapshot["active"]] == [first]
    assert snapshot["current"]["record_id"] == first
