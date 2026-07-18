from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from mail_agent.config import AgentSettings
from mail_agent.models import AttachmentDigest, FinalSummary
from mail_agent.summarization.classification import (
    CLASS_NAME_RU_BY_CODE,
    CLASSIFIER_DEFINITIONS,
    MANUAL_REVIEW_MESSAGE,
    NEW_PROJECT_MESSAGE,
    EmailClassification,
    manual_review_classification,
)
from mail_agent.summarization.prompts import SUMMARY_RECOVERY_SYSTEM, SUMMARY_SYSTEM
from mail_agent.summarization.service import AnalysisService

EXPECTED_CLASS_NAMES = {
    "3D_PRINTERS": "3D-принтеры",
    "CHEMISTRY": "Химия для 3D-печати",
    "FOUNDRY": "Литьё и литейное производство",
    "MOLD_PRINTING": "Печать литейных форм",
    "ROBOTIC_CELLS": "Робототехнические комплексы (РТК)",
    "PRODUCTION_LINES": "Производственные линии",
    "MACHINES": "Станки",
    "TECHNICAL_VISION": "Техническое зрение",
    "OTHER_EQUIPMENT": "Прочее промышленное оборудование",
}


def _classification(code: str) -> EmailClassification:
    if code == "new_project":
        return EmailClassification(
            status="new_project",
            class_code=None,
            class_name_ru=None,
            reason_ru="Предмет письма не соответствует ни одному направлению классификатора.",
            confidence=0.86,
            message_ru=NEW_PROJECT_MESSAGE,
        )
    if code == "manual_review":
        return manual_review_classification("Ключевое вложение недоступно, а других надёжных данных недостаточно.")
    return EmailClassification(
        status="classified",
        class_code=code,  # type: ignore[arg-type]
        class_name_ru=EXPECTED_CLASS_NAMES[code],
        reason_ru="Основной объект запроса соответствует выбранному направлению.",
        confidence=0.91,
        message_ru=f"Класс письма: {code} — {EXPECTED_CLASS_NAMES[code]}",
    )


class ScenarioLLM:
    """Fake LLM проверяет контракт и переданные доказательства без оценки качества модели."""

    def __init__(self, response: EmailClassification) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any], type[object]]] = []

    def structured(self, system: str, user: str, schema: type[object], **_: Any) -> object:
        self.calls.append((system, json.loads(user), schema))
        if schema is FinalSummary:
            return FinalSummary(summary_ru="Итог письма.", classification=self.response, confidence=0.9)
        if schema is AttachmentDigest:
            return AttachmentDigest(summary_ru="Сводка пересланного уровня.", confidence=0.8)
        raise AssertionError(f"Неожиданная схема: {schema}")


def _attachment(text: str, *, status: str = "processed") -> dict[str, object]:
    return {
        "original_filename": "evidence.txt",
        "detected_content_type": "text/plain",
        "size": len(text),
        "status": status,
        "processing_tool": "programmatic",
        "confidence": 0.9,
        "warnings": [],
        "raw_extracted_text": text,
    }


def test_classifier_definition_has_all_codes_and_correct_russian_names() -> None:
    assert len(CLASSIFIER_DEFINITIONS) == 9
    assert CLASS_NAME_RU_BY_CODE == EXPECTED_CLASS_NAMES


def test_email_classification_rejects_unknown_code_and_inconsistent_values() -> None:
    with pytest.raises(ValidationError):
        EmailClassification(
            status="classified",
            class_code="UNKNOWN",
            class_name_ru="Неизвестно",
            reason_ru="Причина.",
            confidence=0.5,
            message_ru="Класс письма.",
        )
    with pytest.raises(ValidationError):
        EmailClassification(
            status="classified",
            class_code=None,
            class_name_ru=None,
            reason_ru="Причина.",
            confidence=0.5,
            message_ru="Класс письма.",
        )
    with pytest.raises(ValidationError):
        EmailClassification(
            status="new_project",
            class_code="MACHINES",
            class_name_ru="Станки",
            reason_ru="Причина.",
            confidence=0.5,
            message_ru=NEW_PROJECT_MESSAGE,
        )


def test_new_project_requires_exact_message_and_manual_review_remains_manual() -> None:
    with pytest.raises(ValidationError):
        EmailClassification(
            status="new_project",
            class_code=None,
            class_name_ru=None,
            reason_ru="Причина.",
            confidence=0.5,
            message_ru="Новый проект",
        )

    result = manual_review_classification()
    assert result.status == "manual_review"
    assert result.message_ru == MANUAL_REVIEW_MESSAGE
    assert result.class_code is None


def test_final_summary_requires_a_classification_object() -> None:
    with pytest.raises(ValidationError):
        FinalSummary.model_validate({"summary_ru": "Итог", "confidence": 0.5})


def test_summary_prompts_contain_classifier_and_overlap_rules() -> None:
    for prompt in (SUMMARY_SYSTEM, SUMMARY_RECOVERY_SYSTEM):
        assert "MOLD_PRINTING" in prompt
        assert "ROBOTIC_CELLS" in prompt
        assert "PRODUCTION_LINES" in prompt
        assert "OTHER_EQUIPMENT" in prompt
        assert "primary requested deliverable" in prompt
        assert NEW_PROJECT_MESSAGE in prompt
        assert "manual_review" in prompt


@pytest.mark.parametrize(
    ("subject", "body", "code"),
    [
        ("Поставка 3D-принтера", "Просим подобрать и поставить промышленный 3D-принтер.", "3D_PRINTERS"),
        ("Фотополимерная смола", "Нужна поставка смолы для 3D-печати.", "CHEMISTRY"),
        ("Печать стержней", "Заказываем услугу печати литейных форм и стержней.", "MOLD_PRINTING"),
        ("Роботизированная сварка", "Требуется роботизированная ячейка для сварки.", "ROBOTIC_CELLS"),
        ("Автоматическая линия", "Нужна линия с обработкой, контролем и упаковкой.", "PRODUCTION_LINES"),
        ("Фрезерный станок", "Просим ТКП на отдельный фрезерный станок.", "MACHINES"),
        ("Контроль дефектов", "Нужна камера и ПО для визуального контроля дефектов.", "TECHNICAL_VISION"),
        ("Литейный участок", "Требуется оборудование для литейного производства.", "FOUNDRY"),
        ("Промышленный компрессор", "Нужен компрессор для производственного участка.", "OTHER_EQUIPMENT"),
        ("Разработка сайта", "Просим разработать корпоративный сайт.", "new_project"),
    ],
)
def test_final_analysis_preserves_mocked_classification_contract(subject: str, body: str, code: str) -> None:
    llm = ScenarioLLM(_classification(code))
    service = AnalysisService(AgentSettings(), llm, ocr=None)  # type: ignore[arg-type]

    result = service.summarize({"subject": subject}, body, [], [])

    assert result.classification == _classification(code)
    final_evidence = next(call[1] for call in llm.calls if call[2] is FinalSummary)
    assert final_evidence["subject"] == subject
    assert final_evidence["body"] == body


def test_final_analysis_uses_forwarded_chain_attachment_text_and_attachment_warnings() -> None:
    llm = ScenarioLLM(_classification("MOLD_PRINTING"))
    service = AnalysisService(AgentSettings(), llm, ocr=None)  # type: ignore[arg-type]
    body = """[Внешний комментарий переславшего]
Проверьте запрос.
[Пересланное сообщение 1]
Тема: Формы
[Содержимое]
Нужна услуга изготовления формы.
[Пересланное сообщение 2]
Тема: Детали
[Содержимое]
Требуются стержни для литья.
"""
    attachment = _attachment("Требуется напечатать мастер-модель.")

    result = service.summarize(
        {"subject": "Fwd: формы", "is_forwarded": True},
        body,
        [attachment],
        ["Вложение было проверено."],
    )

    assert result.classification.class_code == "MOLD_PRINTING"
    final_evidence = next(call[1] for call in llm.calls if call[2] is FinalSummary)
    assert final_evidence["body"] == ""
    assert final_evidence["forwarded_chain"]["summary_ru"] == "Сводка пересланного уровня."
    assert final_evidence["attachments"][0]["extracted_text"] == "Требуется напечатать мастер-модель."
    assert final_evidence["warnings"] == ["Вложение было проверено."]


def test_unavailable_key_attachment_with_insufficient_evidence_keeps_manual_review() -> None:
    llm = ScenarioLLM(_classification("manual_review"))
    service = AnalysisService(AgentSettings(), llm, ocr=None)  # type: ignore[arg-type]
    attachment = _attachment("", status="skipped")
    attachment["warnings"] = ["Не удалось корректно извлечь содержимое файла; требуется ручная проверка."]

    result = service.summarize({"subject": "Запрос"}, "Просим посмотреть вложение.", [attachment], [])

    assert result.classification.status == "manual_review"
    final_evidence = next(call[1] for call in llm.calls if call[2] is FinalSummary)
    assert final_evidence["attachments"][0]["status"] == "skipped"
    assert final_evidence["attachments"][0]["warnings"]
