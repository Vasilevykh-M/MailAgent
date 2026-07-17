"""Маршрутизация нормального и ошибочного исхода узла LangGraph."""

from __future__ import annotations

from ..models import MailProcessingState

_MANUAL_REVIEW_STAGES = {
    "normalize_message",
    "collect_attachment_metadata",
    "plan_attachments",
    "process_attachments",
    "validate_extractions",
    "summarize_message",
    "prepare_api_record",
}


def route_error(state: MailProcessingState) -> str:
    stage = state.get("failed_stage")
    if not stage:
        return "next"
    # Временная ошибка не должна превращаться в обычный итог ручной проверки:
    # checkpoint и журнал позволяют повторить именно упавший узел.
    if state.get("status") == "retryable_error":
        return "failure"
    return "manual_review" if stage in _MANUAL_REVIEW_STAGES else "failure"


def route_after_check(state: MailProcessingState) -> str:
    if state.get("failed_stage"):
        return "failure"
    if state.get("status") == "completed":
        return "end"
    # После подтверждённого API commit не повторяем OCR/LLM: остаются только `\Seen` и `complete`.
    return "mark" if state.get("status") == "result_committed" else "fetch"


def route_after_fetch(state: MailProcessingState) -> str:
    if state.get("failed_stage"):
        return "failure"
    return "mark" if state.get("status") == "result_committed" else "next"
