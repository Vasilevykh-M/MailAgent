from __future__ import annotations

import json
from typing import Any

from mail_agent.config import AgentSettings
from mail_agent.exceptions import LLMResponseFormatError
from mail_agent.models import AttachmentDigest, FinalSummary, OCRCorrection
from mail_agent.summarization.classification import EmailClassification
from mail_agent.summarization.prompts import (
    ATTACHMENT_CHUNK_SYSTEM,
    ATTACHMENT_REDUCE_SYSTEM,
    FORWARDED_MESSAGE_CHUNK_SYSTEM,
    FORWARDED_MESSAGE_REDUCE_SYSTEM,
    MESSAGE_BODY_CHUNK_SYSTEM,
    MESSAGE_BODY_REDUCE_SYSTEM,
    MESSAGE_DIGEST_SYSTEM,
    SPREADSHEET_CHUNK_SYSTEM,
)
from mail_agent.summarization.service import AnalysisService


def _classification() -> EmailClassification:
    return EmailClassification(
        status="classified",
        class_code="3D_PRINTERS",
        class_name_ru="3D-принтеры",
        reason_ru="Запрос относится к поставке промышленного 3D-принтера.",
        confidence=0.9,
        message_ru="Класс письма: 3D_PRINTERS — 3D-принтеры",
    )


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], type[object], dict[str, Any]]] = []

    def structured(self, system: str, user: str, schema: type[object], **kwargs: Any) -> object:
        self.calls.append((system, json.loads(user), schema, kwargs))
        if schema is AttachmentDigest:
            return AttachmentDigest(summary_ru="Краткое содержание", key_facts_ru=["Факт"], confidence=0.9)
        if schema is FinalSummary:
            return FinalSummary(summary_ru="Итог", classification=_classification(), confidence=0.9)
        if schema is EmailClassification:
            return _classification()
        raise AssertionError(f"Неожиданная схема: {schema}")


def _attachment(text: str) -> dict[str, Any]:
    return {
        "original_filename": "large-document.txt",
        "detected_content_type": "text/plain",
        "size": len(text),
        "status": "processed",
        "processing_tool": "programmatic",
        "confidence": 1.0,
        "warnings": [],
        "raw_extracted_text": text,
    }


def test_large_attachment_is_summarized_in_chunks_then_reduced() -> None:
    settings = AgentSettings()
    settings.limits.chunk_size = 1_000
    settings.limits.max_attachment_summary_chunks = 10
    llm = FakeLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "", [_attachment("x" * 2_500)], [])

    chunk_calls = [call for call in llm.calls if call[0] == ATTACHMENT_CHUNK_SYSTEM]
    reduce_calls = [call for call in llm.calls if call[0] == ATTACHMENT_REDUCE_SYSTEM]
    final_call = next(call for call in llm.calls if call[2] is FinalSummary)
    assert result.summary_ru == "Итог"
    assert len(chunk_calls) == 3
    assert len(reduce_calls) == 1
    assert all(len(call[1]["text"]) <= 1_000 for call in chunk_calls)
    assert all(call[3]["max_tokens"] == 600 for call in chunk_calls + reduce_calls)
    assert "extracted_text" not in final_call[1]["attachments"][0]
    assert final_call[1]["attachments"][0]["chunked_summary"]["summary_ru"] == "Краткое содержание"


def test_large_message_body_is_summarized_in_chunks_then_reduced() -> None:
    settings = AgentSettings()
    settings.limits.message_body_chunk_size = 1_000
    settings.llm.max_text_chars_per_request = 6_000
    llm = FakeLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]
    body = "Фрагмент тела письма. " * 180

    result = service.summarize({"subject": "Запрос"}, body, [], [])

    chunk_calls = [call for call in llm.calls if call[0] == MESSAGE_BODY_CHUNK_SYSTEM]
    reduce_calls = [call for call in llm.calls if call[0] == MESSAGE_BODY_REDUCE_SYSTEM]
    final_call = next(call for call in llm.calls if call[2] is FinalSummary)
    assert result.summary_ru == "Итог"
    assert len(chunk_calls) == 4
    assert len(reduce_calls) == 1
    assert all(len(call[1]["text"]) <= 1_000 for call in chunk_calls)
    assert final_call[1]["body"] == ""
    assert final_call[1]["body_digest"]["summary_ru"] == "Краткое содержание"
    assert body[:100] not in json.dumps(final_call[1], ensure_ascii=False)


def test_very_large_message_body_is_sampled_with_visible_warning() -> None:
    settings = AgentSettings()
    settings.limits.message_body_chunk_size = 1_000
    settings.limits.max_message_body_summary_chunks = 2
    settings.llm.max_text_chars_per_request = 6_000
    llm = FakeLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "x" * 4_000, [], [])

    chunk_calls = [call for call in llm.calls if call[0] == MESSAGE_BODY_CHUNK_SYSTEM]
    assert len(chunk_calls) == 2
    assert any("состоит из 4 фрагментов" in warning for warning in result.warnings_ru)


def test_very_large_attachment_is_sampled_with_a_visible_warning() -> None:
    settings = AgentSettings()
    settings.limits.chunk_size = 1_000
    settings.limits.max_attachment_summary_chunks = 2
    llm = FakeLLM()
    attachment = _attachment("x" * 4_000)
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    service.summarize({}, "", [attachment], [])

    chunk_calls = [call for call in llm.calls if call[0] == ATTACHMENT_CHUNK_SYSTEM]
    assert len(chunk_calls) == 2
    assert any("состоит из 4 фрагментов" in warning for warning in attachment["warnings"])


def test_invalid_chunk_response_uses_safe_fallback() -> None:
    class InvalidChunkLLM(FakeLLM):
        def structured(self, system: str, user: str, schema: type[object], **kwargs: Any) -> object:
            if schema is AttachmentDigest:
                raise LLMResponseFormatError("invalid response")
            return super().structured(system, user, schema, **kwargs)

    settings = AgentSettings()
    settings.limits.chunk_size = 1_000
    llm = InvalidChunkLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "", [_attachment("x" * 1_500)], [])

    assert result.summary_ru == "Итог"
    final_call = next(call for call in llm.calls if call[2] is FinalSummary)
    digest = final_call[1]["attachments"][0]["chunked_summary"]
    assert digest["summary_ru"] == (
        "Автоматическую сводку фрагмента получить не удалось; требуется ручная проверка вложения."
    )
    assert digest["warnings_ru"] == [
        "LLM не вернул корректную сводку этого фрагмента; требуется ручная проверка вложения."
    ]
    assert "x" * 100 not in digest["summary_ru"]


def test_invalid_final_response_uses_compact_email_digest_not_message_body() -> None:
    class InvalidFinalLLM(FakeLLM):
        def __init__(self) -> None:
            super().__init__()
            self.final_attempts = 0

        def structured(self, system: str, user: str, schema: type[object], **kwargs: Any) -> object:
            if schema is FinalSummary:
                self.final_attempts += 1
                raise LLMResponseFormatError("invalid response")
            return super().structured(system, user, schema, **kwargs)

    llm = InvalidFinalLLM()
    service = AnalysisService(AgentSettings(), llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "Сырой текст письма, который нельзя записывать как сводку.", [], [])

    assert llm.final_attempts == service.settings.llm.final_summary_attempts
    assert result.summary_ru == "Краткое содержание"
    assert result.classification.status == "classified"
    assert "Сырой текст письма" not in result.summary_ru
    assert "сокращённом режиме" in result.warnings_ru[0]


def test_chunked_body_recovery_uses_digest_not_raw_body() -> None:
    class InvalidFinalLLM(FakeLLM):
        def structured(self, system: str, user: str, schema: type[object], **kwargs: Any) -> object:
            if schema is FinalSummary:
                raise LLMResponseFormatError("invalid response")
            return super().structured(system, user, schema, **kwargs)

    settings = AgentSettings()
    settings.llm.max_text_chars_per_request = 6_000
    settings.limits.message_body_chunk_size = 1_000
    llm = InvalidFinalLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]
    body = "Конфиденциальный маркер тела письма. " * 100

    result = service.summarize({}, body, [], [])

    fallback_call = next(call for call in llm.calls if call[0] == MESSAGE_DIGEST_SYSTEM)
    assert result.summary_ru == "Краткое содержание"
    assert fallback_call[1]["body"] == ""
    assert fallback_call[1]["body_digest"]["summary_ru"] == "Краткое содержание"
    assert body[:100] not in json.dumps(fallback_call[1], ensure_ascii=False)


def test_compact_fallback_uses_manual_review_when_classification_is_unusable() -> None:
    class UnusableClassifierLLM(FakeLLM):
        def structured(self, system: str, user: str, schema: type[object], **kwargs: Any) -> object:
            if schema in {FinalSummary, EmailClassification}:
                raise LLMResponseFormatError("invalid response")
            return super().structured(system, user, schema, **kwargs)

    service = AnalysisService(AgentSettings(), UnusableClassifierLLM(), ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "Содержимое письма для суммаризации.", [], [])

    assert result.summary_ru == "Краткое содержание"
    assert result.classification.status == "manual_review"


def test_final_summary_retries_before_using_recovery_mode() -> None:
    class RetryFinalLLM(FakeLLM):
        def __init__(self) -> None:
            super().__init__()
            self.final_attempts = 0

        def structured(self, system: str, user: str, schema: type[object], **kwargs: Any) -> object:
            if schema is FinalSummary:
                self.final_attempts += 1
                if self.final_attempts < 3:
                    raise LLMResponseFormatError("invalid response")
            return super().structured(system, user, schema, **kwargs)

    settings = AgentSettings()
    settings.llm.final_summary_attempts = 3
    llm = RetryFinalLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "Содержимое письма для суммаризации.", [], [])

    assert result.summary_ru == "Итог"
    assert llm.final_attempts == 3


def test_spreadsheet_uses_structured_prompt_even_when_it_is_small() -> None:
    settings = AgentSettings()
    llm = FakeLLM()
    attachment = _attachment(
        '[Таблица: XLSX]\n[Лист: "ТКП"]\n[Заголовки: Наименование | Цена]\nстрока 2: Наименование=Деталь А; Цена=1500'
    )
    attachment["original_filename"] = "proposal.xlsx"
    attachment["extension"] = ".xlsx"
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "", [attachment], [])

    assert result.summary_ru == "Итог"
    spreadsheet_call = next(call for call in llm.calls if call[0] == SPREADSHEET_CHUNK_SYSTEM)
    assert spreadsheet_call[1]["attachment"]["kind"] == "spreadsheet"
    final_call = next(call for call in llm.calls if call[2] is FinalSummary)
    assert "extracted_text" not in final_call[1]["attachments"][0]


def test_spreadsheet_chunks_repeat_the_sheet_headers() -> None:
    text = '[Таблица: XLSX]\n[Лист: "ТКП"]\n[Заголовки: Наименование | Цена]\n' + "\n".join(
        f"строка {index}: Наименование=Деталь {index}; Цена=1500" for index in range(1, 80)
    )

    chunks = AnalysisService._spreadsheet_chunks(text, 1_000)

    assert len(chunks) > 1
    assert all('[Лист: "ТКП"]' in chunk for chunk in chunks)
    assert all("[Заголовки: Наименование | Цена]" in chunk for chunk in chunks)


def test_forwarded_chain_is_summarized_by_each_level_before_final_summary() -> None:
    settings = AgentSettings()
    llm = FakeLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]
    body = """[Внешний комментарий переславшего]
Пожалуйста, возьмите в работу.
[Пересланное сообщение 1]
Тема: Запрос ТКП
[Содержимое]
Согласуйте техническое решение.
[Пересланное сообщение 2]
Тема: Исходный запрос
[Содержимое]
Просим направить ТКП.
"""

    result = service.summarize({"is_forwarded": True}, body, [], [])

    assert result.summary_ru == "Итог"
    chunk_calls = [call for call in llm.calls if call[0] == FORWARDED_MESSAGE_CHUNK_SYSTEM]
    reduce_calls = [call for call in llm.calls if call[0] == FORWARDED_MESSAGE_REDUCE_SYSTEM]
    assert len(chunk_calls) == 3
    assert reduce_calls
    final_call = next(call for call in llm.calls if call[2] is FinalSummary)
    assert final_call[1]["body"] == ""
    assert final_call[1]["forwarded_chain"]["summary_ru"] == "Краткое содержание"


def test_forwarded_chain_has_a_global_chunk_limit_and_visible_warning() -> None:
    settings = AgentSettings()
    settings.limits.chunk_size = 1_000
    settings.limits.max_forwarded_summary_chunks = 2
    llm = FakeLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]
    body = (
        "[Внешний комментарий переславшего]\n"
        + "a" * 2_000
        + "\n[Пересланное сообщение 1]\n[Содержимое]\n"
        + "b" * 2_000
    )

    result = service.summarize({"is_forwarded": True}, body, [], [])

    chunk_calls = [call for call in llm.calls if call[0] == FORWARDED_MESSAGE_CHUNK_SYSTEM]
    assert len(chunk_calls) == 2
    assert any("превышает лимит анализа" in warning for warning in result.warnings_ru)


def test_unreadable_attachment_is_always_reported_in_final_summary() -> None:
    settings = AgentSettings()
    llm = FakeLLM()
    attachment = _attachment("")
    attachment["original_filename"] = "broken.xlsx"
    attachment["extension"] = ".xlsx"
    attachment["status"] = "skipped"
    attachment["warnings"] = ["Не удалось корректно извлечь содержимое таблицы; требуется ручная проверка файла."]
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({}, "", [attachment], [])

    notice = "broken.xlsx: не удалось корректно обработать файл; требуется ручная проверка."
    assert notice in result.attachment_summaries
    assert notice in result.warnings_ru


def test_skipped_attachment_does_not_replace_forwarded_email_evidence() -> None:
    settings = AgentSettings()
    llm = FakeLLM()
    attachment = _attachment("Неразборчивый текст вложения, который нельзя отправлять в сводку.")
    attachment["original_filename"] = "broken.pdf"
    attachment["status"] = "skipped"
    attachment["warnings"] = ["Не удалось корректно извлечь содержимое файла; требуется ручная проверка."]
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]
    body = """[Пересланное сообщение 1]
Тема: Запрос ТКП
[Содержимое]
Просим направить ТКП до конца недели.
"""

    result = service.summarize({"is_forwarded": True}, body, [attachment], [])

    final_call = next(call for call in llm.calls if call[2] is FinalSummary)
    evidence = final_call[1]
    assert result.summary_ru == "Итог"
    assert evidence["body"] == ""
    assert evidence["forwarded_chain"]["summary_ru"] == "Краткое содержание"
    assert "extracted_text" not in evidence["attachments"][0]
    assert "Неразборчивый текст вложения" not in json.dumps(evidence, ensure_ascii=False)
    assert "broken.pdf: не удалось корректно обработать файл; требуется ручная проверка." in result.attachment_summaries


def test_ocr_correction_uses_reserved_completion_budget() -> None:
    class CorrectionLLM(FakeLLM):
        def structured(self, system: str, user: str, schema: type[object], **kwargs: Any) -> object:
            self.calls.append((system, json.loads(user), schema, kwargs))
            if schema is OCRCorrection:
                return OCRCorrection(corrected_text="Исправленный текст", confidence=0.9)
            raise AssertionError(f"Неожиданная схема: {schema}")

    settings = AgentSettings()
    settings.llm.max_ocr_correction_tokens = 3_000
    llm = CorrectionLLM()
    service = AnalysisService(settings, llm, ocr=None)  # type: ignore[arg-type]

    result = service.correct_ocr("Исходный OCR", 0.5, {})

    assert result.corrected_text == "Исправленный текст"
    assert llm.calls[0][3]["max_tokens"] == 3_000
