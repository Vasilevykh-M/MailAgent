from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from mail_agent.config import AgentSettings, LimitsSettings, RetrySettings
from mail_agent.exceptions import ExternalServiceError, OCRServiceError, PermanentError
from mail_agent.graph.builder import MessageGraph
from mail_agent.models import AttachmentMeta, AttachmentPlan, FinalSummary, MessageReference
from mail_agent.storage.processing_repository import ProcessingRepository, record_id
from mail_agent.summarization.classification import EmailClassification


def _classification() -> EmailClassification:
    return EmailClassification(
        status="classified",
        class_code="OTHER_EQUIPMENT",
        class_name_ru="Прочее промышленное оборудование",
        reason_ru="Письмо связано с промышленным оборудованием вне специальных направлений.",
        confidence=0.7,
        message_ru="Класс письма: OTHER_EQUIPMENT — Прочее промышленное оборудование",
    )


class Mail:
    def __init__(self) -> None:
        self.events: list[str] = []

    def fetch_message(self, uid: str, mailbox: str):
        self.events.append("fetch")
        return {
            "uid": uid,
            "mailbox": mailbox,
            "message_id": "<one>",
            "headers": [["X", "Y"], ["X", "Z"]],
            "text_plain": "body",
            "text_html": "<p>html</p>",
            "raw_bytes": b"From: sender@example.test\r\nSubject: subject\r\n\r\nbody",
            "attachments": [],
            "flags": [],
            "from": "sender",
            "to": [],
            "cc": [],
            "bcc": [],
            "reply_to": [],
            "subject": "subject",
            "date": None,
        }

    def mark_read(self, uid: str, mailbox: str) -> None:
        self.events.append("read")


class Analysis:
    settings = SimpleNamespace(limits=LimitsSettings(), mail=SimpleNamespace(max_message_size=100_000))

    def summarize(self, message, body, attachments, warnings):
        return FinalSummary(summary_ru="итог", classification=_classification(), confidence=1)


class ResultsAPI:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.results: list[dict[str, object]] = []
        self.payloads: list[dict[str, object]] = []

    def persist(self, payload, *, raw_email_path, attachment_paths):
        del raw_email_path, attachment_paths
        self.events.append("api")
        self.payloads.append(payload)
        self.results.append(
            {
                "summary": payload["agent_result"]["summary"],
                "attachments": payload["agent_result"]["attachments"],
            }
        )
        return SimpleNamespace(model_dump=lambda mode="json": {"status": "committed", "storage_verified": True})


class FailingResultsAPI(ResultsAPI):
    def __init__(self, events: list[str]) -> None:
        super().__init__(events)
        self.calls = 0

    def persist(self, payload, *, raw_email_path, attachment_paths):
        self.calls += 1
        self.events.append("api")
        if self.calls == 1:
            raise ExternalServiceError("temporary Results API failure")
        del raw_email_path, attachment_paths
        self.results.append(
            {
                "summary": payload["agent_result"]["summary"],
                "attachments": payload["agent_result"]["attachments"],
            }
        )
        return SimpleNamespace(model_dump=lambda mode="json": {"status": "committed", "storage_verified": True})


class FailingOCR:
    def __init__(self) -> None:
        self.calls = 0

    def process(self, *args, **kwargs):
        self.calls += 1
        raise OCRServiceError("OCR unavailable")


class VisionLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def structured(self, system, user, schema, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text="Текст от VLM", confidence=0.7)


class FallbackAnalysis:
    def __init__(self) -> None:
        self.settings = AgentSettings()
        self.ocr = FailingOCR()
        self.llm = VisionLLM()

    def plan(self, meta, parsed):
        raise OCRServiceError("OCR capabilities unavailable")


class FailingSummaryAnalysis(Analysis):
    def summarize(self, message, body, attachments, warnings):
        raise PermanentError("Текст письма не должен попасть в диагностику.")


class RetryableSummaryAnalysis(Analysis):
    def __init__(self) -> None:
        self.summarize_calls = 0

    def summarize(self, message, body, attachments, warnings):
        self.summarize_calls += 1
        if self.summarize_calls == 1:
            raise ExternalServiceError("temporary summary failure")
        return FinalSummary(summary_ru="итог после повтора", classification=_classification(), confidence=1)


class RetryableReadMail(Mail):
    def __init__(self) -> None:
        super().__init__()
        self.read_calls = 0

    def mark_read(self, uid: str, mailbox: str) -> None:
        self.read_calls += 1
        self.events.append("read")
        if self.read_calls == 1:
            raise ExternalServiceError("temporary seen failure")


class BinaryAttachmentMail(Mail):
    payload = b"\x00\xff\x01\xfe\x80\x81\x10\x11"

    def fetch_message(self, uid: str, mailbox: str):
        message = super().fetch_message(uid, mailbox)
        message["attachments"] = [
            {"filename": "note.bin", "content_type": "application/octet-stream", "data": self.payload}
        ]
        message["text_plain"] = "private-body-marker-must-not-reach-logs"
        return message


class ProgrammaticAttachmentAnalysis(Analysis):
    def plan(self, meta, parsed):
        return AttachmentPlan(tool="programmatic", confidence=1, reason="local test extraction")


class AttachmentFailureMail(Mail):
    def fetch_message(self, uid: str, mailbox: str):
        message = super().fetch_message(uid, mailbox)
        message["text_plain"] = """---------- Пересланное сообщение ----------
От: АО КМЗ <sales@example.test>
Тема: Запрос ТКП

Просим направить ТКП до конца недели.
"""
        message["attachments"] = [
            {
                "filename": "КМЗ_ТКП.png",
                "content_type": "image/png",
                "data": b"\x89PNG\r\n\x1a\nattachment",
            },
            {
                "filename": "примечание.txt",
                "content_type": "text/plain",
                "data": b"Second attachment must still be processed.",
            },
        ]
        return message


class FailingAttachmentLLM:
    def structured(self, *args, **kwargs):
        raise PermanentError("Вложение не обработано")


class AttachmentFailureAnalysis(Analysis):
    def __init__(self) -> None:
        self.settings = AgentSettings()
        self.llm = FailingAttachmentLLM()
        self.ocr = None
        self.received_body = ""
        self.received_attachments = []

    def plan(self, meta, parsed):
        tool = "vision" if meta.extension == ".png" else "programmatic"
        return AttachmentPlan(tool=tool, confidence=0.5, reason="test")

    def summarize(self, message, body, attachments, warnings):
        self.received_body = body
        self.received_attachments = attachments
        return FinalSummary(summary_ru="Сводка текста пересылки", classification=_classification(), confidence=0.8)


def _image_attachment(path: Path) -> AttachmentMeta:
    path.write_bytes(b"safe test image")
    return AttachmentMeta(
        original_filename="scan.png",
        safe_filename="scan-safe.png",
        content_type="image/png",
        detected_content_type="image/png",
        extension=".png",
        size=path.stat().st_size,
        sha256="a" * 64,
        is_inline=False,
        file_path=str(path),
    )


def test_langgraph_commits_api_before_seen_and_preserves_duplicate_headers(tmp_path) -> None:
    mail = Mail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    results_api = ResultsAPI(mail.events)
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=Analysis(),
        results_api=results_api,
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        state = graph.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path)
    finally:
        graph.close()
    assert state["status"] == "completed"
    assert mail.events == ["fetch", "api", "read"]
    assert state["message_metadata"]["headers"] == [["X", "Y"], ["X", "Z"]]
    assert state["summary"]["classification"]["status"] == "classified"
    assert results_api.payloads[-1]["agent_result"]["summary"]["classification"]["status"] == "classified"


def test_langgraph_recovery_after_result_commit_retries_only_seen(tmp_path) -> None:
    mail = Mail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    stable = repository.ensure("INBOX", "1", "<one>", "1")
    repository.start(stable)
    repository.result_committed(stable, {"request_id": "test"})
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=Analysis(),
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        state = graph.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path)
    finally:
        graph.close()
    assert state["status"] == "completed"
    assert mail.events == ["read"]
    assert repository.get(record_id("INBOX", "1", "<one>"))["status"] == "completed"


def test_graph_writes_manual_review_record_when_summarization_fails(tmp_path, caplog) -> None:
    mail = Mail()
    results_api = ResultsAPI(mail.events)
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=FailingSummaryAnalysis(),
        results_api=results_api,
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    caplog.set_level(logging.INFO)
    try:
        state = graph.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path)
    finally:
        graph.close()

    item = repository.get(record_id("INBOX", "1", "<one>"))
    assert item is not None
    assert state["status"] == "completed"
    assert mail.events == ["fetch", "api", "read"]
    assert item["status"] == "completed"
    assert item["requires_manual_review"] == 1
    assert item["manual_review_stage"] == "summarize_message"
    assert item["manual_review_error_type"] == "PermanentError"
    assert state["summary"]["summary_ru"] == "Автоматическая обработка не завершена. Письмо требует ручной проверки."
    assert state["summary"]["classification"]["status"] == "manual_review"
    assert results_api.results[-1]["summary"]["confidence"] == 0
    assert results_api.results[-1]["summary"]["classification"]["status"] == "manual_review"
    assert state["errors"][-1] == {"stage": "summarize_message", "type": "PermanentError"}
    assert "manual_review_record_created" in [record.getMessage() for record in caplog.records]
    assert "Текст письма не должен" not in caplog.text


def test_manual_review_names_unprocessed_attachments_without_extracted_text(tmp_path) -> None:
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    stable = repository.ensure("INBOX", "1", "<one>", "1")
    graph = MessageGraph(
        mail=Mail(),
        repository=repository,
        analysis=Analysis(),
        results_api=ResultsAPI([]),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        result = graph._manual_review(
            {
                "record_id": stable,
                "mailbox": "INBOX",
                "uid": "1",
                "failed_stage": "summarize_message",
                "errors": [{"stage": "summarize_message", "type": "LLMResponseFormatError"}],
                "attachment_results": [
                    {
                        "original_filename": "КМЗ_ТКП.xlsx",
                        "raw_extracted_text": "Сырой текст таблицы, который не должен попасть в сводку.",
                    }
                ],
            }
        )
    finally:
        graph.close()

    summary = result["summary"]
    assert summary["attachment_summaries"] == [
        "КМЗ_ТКП.xlsx: автоматическую обработку вложения не удалось завершить; требуется ручная проверка."
    ]
    assert "Сырой текст таблицы" not in summary["summary_ru"]
    assert "Сырой текст таблицы" not in summary["attachment_summaries"][0]
    assert summary["classification"]["status"] == "manual_review"


def test_attachment_failure_keeps_forwarded_email_summary_flow(tmp_path) -> None:
    mail = AttachmentFailureMail()
    analysis = AttachmentFailureAnalysis()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    results_api = ResultsAPI(mail.events)
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=results_api,
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        state = graph.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path)
    finally:
        graph.close()

    assert state["status"] == "completed"
    assert mail.events == ["fetch", "api", "read"]
    assert "Просим направить ТКП до конца недели." in analysis.received_body
    assert len(analysis.received_attachments) == 2
    assert analysis.received_attachments[0]["status"] == "skipped"
    assert analysis.received_attachments[0]["raw_extracted_text"] is None
    assert analysis.received_attachments[1]["status"] == "processed"
    assert analysis.received_attachments[1]["raw_extracted_text"] == "Second attachment must still be processed."
    assert state["summary"]["summary_ru"] == "Сводка текста пересылки"
    assert state["summary"]["attachment_summaries"] == [
        "КМЗ_ТКП.png: не удалось корректно обработать файл; требуется ручная проверка."
    ]
    item = repository.get(record_id("INBOX", "1", "<one>"))
    assert item is not None
    assert item["requires_manual_review"] == 1
    assert item["manual_review_stage"] == "process_attachments"
    assert item["manual_review_error_type"] == "AttachmentProcessingUnavailable"


def test_graph_logs_stage_lifecycle_without_message_body(tmp_path, caplog) -> None:
    mail = Mail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=Analysis(),
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    caplog.set_level(logging.INFO)
    try:
        graph.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path)
    finally:
        graph.close()

    events = [record.getMessage() for record in caplog.records]
    assert "graph_run_started" in events
    assert "stage_started" in events
    assert "stage_completed" in events
    assert "graph_run_completed" in events
    assert all("body" not in record.getMessage() for record in caplog.records)


def test_ocr_service_failure_uses_vlm_fallback_for_image(tmp_path) -> None:
    mail = Mail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    analysis = FallbackAnalysis()
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    attachment = _image_attachment(tmp_path / "scan.png")
    stable = repository.ensure("INBOX", "1", "<one>", "1")
    plan = AttachmentPlan(
        tool="ocr",
        language="ru",
        ocr_task="ocr",
        ocr_model="pp-ocrv5",
        confidence=0.1,
        reason="scanned image",
    )
    try:
        result = graph._process(
            {
                "record_id": stable,
                "attachments": [attachment.model_dump(mode="json")],
                "attachment_plans": [plan.model_dump(mode="json")],
            }
        )
    finally:
        graph.close()

    processed = result["attachment_results"][0]
    assert analysis.ocr.calls == 1
    assert processed["processing_tool"] == "vision"
    assert processed["raw_extracted_text"] == "Текст от VLM"
    assert any("извлечён через VLM" in warning for warning in processed["warnings"])
    assert analysis.llm.calls[0]["images"] == [("image/png", b"safe test image")]
    assert analysis.llm.calls[0]["max_tokens"] == analysis.settings.llm.max_ocr_correction_tokens


def test_ocr_capabilities_failure_plans_vlm_fallback(tmp_path) -> None:
    mail = Mail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    analysis = FallbackAnalysis()
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    attachment = _image_attachment(tmp_path / "scan.png")
    try:
        result = graph._plan({"attachments": [attachment.model_dump(mode="json")]})
    finally:
        graph.close()

    plan = result["attachment_plans"][0]
    assert plan["tool"] == "vision"
    assert any("визуальное извлечение" in warning for warning in plan["validation_warnings"])


def test_forwarded_message_uses_original_metadata_and_body(tmp_path) -> None:
    mail = Mail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=Analysis(),
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    stable = repository.ensure("INBOX", "1", "<one>", "1")
    message = {
        "from": "Переславший <forwarder@example.test>",
        "date": "2026-07-12T10:00:00+00:00",
        "subject": "Fwd: Вх письмо 613",
        "to": ["agent@example.test"],
        "text_plain": """См. исходное письмо.

---------- Пересланное сообщение ----------
От: АО КМЗ <sales@example.test>
Дата: 09.07.2026 10:30
Тема: Вх письмо 613 от 09.07.2026 АО КМЗ Запрос ТКП

Просим направить ТКП.
""",
        "text_html": "",
    }
    try:
        result = graph._normalize({"record_id": stable, "message_metadata": message, "warnings": []})
    finally:
        graph.close()

    normalized = result["message_metadata"]
    assert normalized["from"] == "АО КМЗ <sales@example.test>"
    assert normalized["date"] == "09.07.2026 10:30"
    assert normalized["subject"] == "Вх письмо 613 от 09.07.2026 АО КМЗ Запрос ТКП"
    assert normalized["forwarded_by"] == "Переславший <forwarder@example.test>"
    assert result["normalized_body"] == (
        "[Внешний комментарий переславшего]\nСм. исходное письмо.\n"
        "[Пересланное сообщение 1]\n"
        "Отправитель: АО КМЗ <sales@example.test>\n"
        "Дата: 09.07.2026 10:30\n"
        "Тема: Вх письмо 613 от 09.07.2026 АО КМЗ Запрос ТКП\n"
        "[Содержимое]\nПросим направить ТКП."
    )
    assert "Письмо является пересылкой" in result["warnings"][0]


def test_restart_retries_only_failed_summarization_and_keeps_node_history(tmp_path) -> None:
    mail = Mail()
    analysis = RetryableSummaryAnalysis()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    first = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        failed = first.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path / "first")
    finally:
        first.close()

    assert failed["status"] == "retryable_error"
    second = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        completed = second.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path / "second")
    finally:
        second.close()

    stable = record_id("INBOX", "1", "<one>")
    summary = repository.get_node_execution(stable, "summarize_message")
    assert completed["status"] == "completed"
    assert mail.events == ["fetch", "api", "read"]
    assert analysis.summarize_calls == 2
    assert summary is not None
    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 2
    assert summary["previous_status"] == "retryable_error"
    assert summary["started_at"] and summary["completed_at"]
    assert [item["status"] for item in repository.node_attempt_history(str(summary["execution_key"]))] == [
        "retryable_error",
        "completed",
    ]


def test_restart_after_api_failure_retries_only_api_and_downstream_nodes(tmp_path) -> None:
    mail = Mail()
    analysis = Analysis()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    results_api = FailingResultsAPI(mail.events)
    reference = MessageReference(uid="1", mailbox="INBOX", message_id="<one>")
    first = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=results_api,
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        assert first.run(reference, tmp_path / "first")["status"] == "retryable_error"
    finally:
        first.close()
    second = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=results_api,
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        assert second.run(reference, tmp_path / "second")["status"] == "completed"
    finally:
        second.close()

    assert mail.events == ["fetch", "api", "api", "read"]
    assert results_api.calls == 2


def test_restart_after_api_commit_retries_only_seen_and_complete(tmp_path) -> None:
    mail = RetryableReadMail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    results_api = ResultsAPI(mail.events)
    reference = MessageReference(uid="1", mailbox="INBOX", message_id="<one>")
    first = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=Analysis(),
        results_api=results_api,
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        assert first.run(reference, tmp_path / "first")["status"] == "retryable_error"
    finally:
        first.close()
    second = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=Analysis(),
        results_api=results_api,
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    try:
        assert second.run(reference, tmp_path / "second")["status"] == "completed"
    finally:
        second.close()

    assert mail.events == ["fetch", "api", "read", "read"]
    assert results_api.results and len(results_api.results) == 1
    assert repository.get(record_id("INBOX", "1", "<one>"))["status"] == "completed"


def test_pipeline_version_and_full_reprocess_invalidate_completed_node_results(tmp_path) -> None:
    mail = Mail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    reference = MessageReference(uid="1", mailbox="INBOX", message_id="<one>")

    def run(version: str, directory: str) -> None:
        graph = MessageGraph(
            mail=mail,
            repository=repository,
            analysis=Analysis(),
            results_api=ResultsAPI(mail.events),
            checkpoint_db=tmp_path / "check.sqlite",
            pipeline_version=version,
        )
        try:
            assert graph.run(reference, tmp_path / directory)["status"] == "completed"
        finally:
            graph.close()

    run("1", "first")
    run("2", "version-change")
    stable = record_id("INBOX", "1", "<one>")
    assert repository.requeue_for_reprocess(stable)
    run("2", "reprocess")
    assert mail.events == ["fetch", "api", "read", "fetch", "api", "read", "fetch", "api", "read"]


def test_binary_payload_is_not_checkpointed_or_logged_and_stale_paths_are_not_reused(tmp_path, caplog) -> None:
    mail = BinaryAttachmentMail()
    repository = ProcessingRepository(tmp_path / "state.sqlite", RetrySettings())
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=ProgrammaticAttachmentAnalysis(),
        results_api=ResultsAPI(mail.events),
        checkpoint_db=tmp_path / "check.sqlite",
        pipeline_version="1",
    )
    caplog.set_level(logging.INFO)
    try:
        state = graph.run(MessageReference(uid="1", mailbox="INBOX", message_id="<one>"), tmp_path / "work")
        assert state["attachments"][0]["file_path"] is None
        assert (
            graph._hydrate_attachment_paths(
                {"attachments": [{"sha256": "a" * 64, "file_path": str(tmp_path / "missing-attachment.txt")}]}
            )
            == {}
        )
    finally:
        graph.close()

    assert BinaryAttachmentMail.payload not in (tmp_path / "check.sqlite").read_bytes()
    assert b"From: sender@example.test" not in (tmp_path / "check.sqlite").read_bytes()
    assert "private-body-marker-must-not-reach-logs" not in caplog.text
