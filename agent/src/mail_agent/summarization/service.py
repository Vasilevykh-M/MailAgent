"""Выбор инструмента, проверка OCR и сводка с Pydantic-контрактами."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..attachments.parsers import ParsedText
from ..clients.llm import LLMClient
from ..clients.ocr import OCRClient
from ..config import AgentSettings
from ..exceptions import LLMResponseFormatError, PermanentError
from ..logging import log_event
from ..models import AttachmentDigest, AttachmentMeta, AttachmentPlan, FinalSummary, OCRCorrection, ToolName
from .classification import EmailClassification, manual_review_classification
from .prompts import (
    ATTACHMENT_CHUNK_SYSTEM,
    ATTACHMENT_REDUCE_SYSTEM,
    CLASSIFICATION_SYSTEM,
    CORRECTION_SYSTEM,
    FORWARDED_MESSAGE_CHUNK_SYSTEM,
    FORWARDED_MESSAGE_REDUCE_SYSTEM,
    MESSAGE_BODY_CHUNK_SYSTEM,
    MESSAGE_BODY_REDUCE_SYSTEM,
    MESSAGE_DIGEST_SYSTEM,
    ROUTING_SYSTEM,
    SPREADSHEET_CHUNK_SYSTEM,
    SPREADSHEET_REDUCE_SYSTEM,
    SUMMARY_RECOVERY_SYSTEM,
    SUMMARY_SYSTEM,
)

LOGGER = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, settings: AgentSettings, llm: LLMClient, ocr: OCRClient) -> None:
        self.settings, self.llm, self.ocr = settings, llm, ocr

    def plan(self, meta: AttachmentMeta, parsed: ParsedText) -> AttachmentPlan:
        capabilities = self.ocr.capabilities()
        features = {
            "filename": meta.original_filename,
            "size": meta.size,
            "declared_mime": meta.content_type,
            "detected_mime": meta.detected_content_type,
            "extension": meta.extension,
            "page_count": parsed.page_count,
            "has_text_layer": meta.has_text_layer,
            "extracted_text_length": len(parsed.text),
            "usable_local_text": parsed.usable,
            "vision_formats": ["image/jpeg", "image/png", "image/webp"],
            "ocr_capabilities": capabilities,
            "limits": self.settings.limits.model_dump(mode="json"),
        }
        user = "Choose a tool for this attachment metadata:\n" + json.dumps(features, ensure_ascii=False)
        plan = self.llm.structured(ROUTING_SYSTEM, user, AttachmentPlan)
        return self._validate_plan(plan, meta, parsed, capabilities)

    def _validate_plan(
        self, plan: AttachmentPlan, meta: AttachmentMeta, parsed: ParsedText, capabilities: dict[str, Any]
    ) -> AttachmentPlan:
        warnings: list[str] = []
        if plan.tool == "programmatic" and not parsed.usable:
            warnings.append("Локальное извлечение недостаточно качественное.")
        if plan.tool == "vision" and meta.detected_content_type not in {
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
        }:
            warnings.append("Vision допускается только для JPEG, PNG и WebP.")
        if plan.tool == "vision" and meta.size > self.settings.llm.max_image_bytes_per_request:
            warnings.append("Размер вложения превышает лимит изображения для LLM.")
        if plan.tool == "ocr":
            task = plan.ocr_task or "ocr"
            item = capabilities.get("tasks", {}).get(task, {})
            models = {entry.get("id"): entry for entry in item.get("models", []) if isinstance(entry, dict)}
            model = plan.ocr_model or item.get("default_model")
            language = plan.language or item.get("default_language")
            if not isinstance(model, str) or model not in models:
                warnings.append("OCR-модель отсутствует в capabilities.")
            elif not isinstance(language, str) or language not in models[model].get("languages", []):
                warnings.append("Язык не совместим с OCR-моделью.")
            elif meta.detected_content_type not in item.get("supported_mime_types", []):
                warnings.append("Формат не поддерживается выбранной OCR-задачей.")
            else:
                plan.ocr_task, plan.ocr_model, plan.language = task, model, language
        if warnings:
            # Safe deterministic fallback after an invalid model decision. It does not silently trust it.
            fallback: ToolName = (
                "programmatic"
                if parsed.usable
                else "ocr"
                if meta.detected_content_type in {"image/jpeg", "image/png", "application/pdf"}
                else "skip"
            )
            if fallback == "ocr":
                task = "ocr"
                item = capabilities["tasks"].get(task, {})
                plan.ocr_task, plan.ocr_model, plan.language = (
                    task,
                    item.get("default_model"),
                    item.get("default_language"),
                )
            plan.tool = fallback
            plan.validation_warnings.extend(warnings)
        return plan

    def correct_ocr(
        self, raw_text: str, confidence: float, structure: dict[str, Any], image: tuple[str, bytes] | None = None
    ) -> OCRCorrection:
        payload = {"raw_ocr_text": raw_text, "confidence": confidence, "structure": structure}
        return self.llm.structured(
            CORRECTION_SYSTEM,
            json.dumps(payload, ensure_ascii=False),
            OCRCorrection,
            images=[image] if image else None,
            max_tokens=self.settings.llm.max_ocr_correction_tokens,
        )

    @staticmethod
    def _shorten(value: object, limit: int) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        marker = "\n[Фрагмент сокращён для суммаризации.]\n"
        if limit <= len(marker):
            return text[:limit]
        available = max(0, limit - len(marker))
        prefix = available * 2 // 3
        suffix_length = available - prefix
        suffix = text[-suffix_length:] if suffix_length else ""
        return text[:prefix] + marker + suffix

    @classmethod
    def _strings(cls, value: object, *, count: int, item_limit: int) -> list[str]:
        if not isinstance(value, list):
            return []
        return [cls._shorten(item, item_limit) for item in value[:count]]

    def _attachment_metadata(self, attachment: dict[str, Any]) -> dict[str, Any]:
        return {
            "filename": self._shorten(attachment.get("original_filename"), 300),
            "mime_type": self._shorten(attachment.get("detected_content_type"), 120),
            "kind": "spreadsheet" if self._is_spreadsheet(attachment) else "document",
            "size_bytes": attachment.get("size"),
            "status": self._shorten(attachment.get("status"), 80),
            "tool": self._shorten(attachment.get("processing_tool"), 80),
            "confidence": attachment.get("confidence"),
            "warnings": self._strings(attachment.get("warnings"), count=10, item_limit=300),
        }

    def _digest_evidence(self, digest: AttachmentDigest) -> dict[str, Any]:
        return {
            "summary_ru": self._shorten(digest.summary_ru, 350),
            "key_facts_ru": self._strings(digest.key_facts_ru, count=4, item_limit=120),
            "action_items_ru": self._strings(digest.action_items_ru, count=4, item_limit=120),
            "deadlines": self._strings(digest.deadlines, count=4, item_limit=80),
            "warnings_ru": self._strings(digest.warnings_ru, count=4, item_limit=120),
            "confidence": digest.confidence,
        }

    @staticmethod
    def _attachment_text(attachment: dict[str, Any]) -> str:
        value = attachment.get("corrected_text") or attachment.get("raw_extracted_text") or ""
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _is_spreadsheet(attachment: dict[str, Any]) -> bool:
        return str(attachment.get("extension") or "").casefold() in {".xls", ".xlsx"}

    def _append_attachment_warning(self, attachment: dict[str, Any], warning: str) -> None:
        current = attachment.get("warnings")
        warnings = list(current) if isinstance(current, list) else []
        if warning not in warnings:
            warnings.append(warning)
        attachment["warnings"] = warnings

    @staticmethod
    def _spreadsheet_chunks(text: str, size: int) -> list[str]:
        """Делит XLS/XLSX только между строками, повторяя активные заголовки листа."""

        chunks: list[str] = []
        current: list[str] = []
        spreadsheet: str | None = None
        sheet: str | None = None
        headers: str | None = None

        def flush() -> None:
            if current:
                chunks.append("\n".join(current))

        def context() -> list[str]:
            return [value for value in (spreadsheet, sheet, headers) if value]

        def contains_data() -> bool:
            return any(line.startswith(("Преамбула, строка ", "строка ", "Итог, строка ")) for line in current)

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("[Таблица:"):
                spreadsheet = line
                continue
            if line.startswith("[Лист:"):
                if contains_data():
                    flush()
                current.clear()
                sheet, headers = line, None
                current.extend(context())
                continue
            if line.startswith("[Заголовки:"):
                headers = line
                if not current:
                    current.extend(value for value in (spreadsheet, sheet) if value)
                current.append(line)
                continue
            if not current:
                current.extend(context())
            prospective = "\n".join([*current, line])
            if contains_data() and len(prospective) > size:
                flush()
                current.clear()
                current.extend(context())
            if len(line) > size:
                line = AnalysisService._shorten(line, size)
            current.append(line)
        flush()
        return chunks or [text]

    def _select_chunks(self, attachment: dict[str, Any], text: str) -> list[tuple[int, int, str]]:
        size = min(self.settings.limits.chunk_size, max(1_000, self.settings.llm.max_text_chars_per_request // 2))
        source = (
            self._spreadsheet_chunks(text, size)
            if self._is_spreadsheet(attachment)
            else [text[offset : offset + size] for offset in range(0, len(text), size)]
        )
        total = len(source)
        maximum = self.settings.limits.max_attachment_summary_chunks
        if total <= maximum:
            return [(index + 1, total, chunk) for index, chunk in enumerate(source)]
        if maximum == 1:
            indices = [0]
        else:
            indices = sorted({round(index * (total - 1) / (maximum - 1)) for index in range(maximum)})
        self._append_attachment_warning(
            attachment,
            f"Текст вложения состоит из {total} фрагментов; для суммаризации выбрано {len(indices)} фрагментов.",
        )
        return [(index + 1, total, source[index]) for index in indices]

    def _digest(self, system: str, evidence: dict[str, Any]) -> AttachmentDigest:
        try:
            return self.llm.structured(
                system,
                json.dumps(evidence, ensure_ascii=False),
                AttachmentDigest,
                max_tokens=min(600, self.settings.llm.max_completion_tokens),
            )
        except LLMResponseFormatError:
            return AttachmentDigest(
                summary_ru="Автоматическую сводку фрагмента получить не удалось; требуется ручная проверка вложения.",
                warnings_ru=["LLM не вернул корректную сводку этого фрагмента; требуется ручная проверка вложения."],
                confidence=0,
            )

    def _reduce_digests(
        self, metadata: dict[str, Any], digests: list[AttachmentDigest], reduce_system: str
    ) -> AttachmentDigest:
        current = digests
        group_budget = max(1_000, self.settings.llm.max_text_chars_per_request - 2_500)
        while len(current) > 1:
            groups: list[list[dict[str, Any]]] = []
            group: list[dict[str, Any]] = []
            for digest in current:
                value = self._digest_evidence(digest)
                prospective = group + [value]
                if group and len(json.dumps({"partial_summaries": prospective}, ensure_ascii=False)) > group_budget:
                    groups.append(group)
                    group = [value]
                else:
                    group = prospective
            if group:
                groups.append(group)
            current = [
                self._digest(reduce_system, {"attachment": metadata, "partial_summaries": group}) for group in groups
            ]
        return current[0]

    def _chunked_attachment_summary(self, attachment: dict[str, Any], text: str) -> dict[str, Any]:
        metadata = self._attachment_metadata(attachment)
        spreadsheet = self._is_spreadsheet(attachment)
        chunk_system = SPREADSHEET_CHUNK_SYSTEM if spreadsheet else ATTACHMENT_CHUNK_SYSTEM
        reduce_system = SPREADSHEET_REDUCE_SYSTEM if spreadsheet else ATTACHMENT_REDUCE_SYSTEM
        digests = [
            self._digest(
                chunk_system,
                {
                    "attachment": metadata,
                    "chunk_number": index,
                    "chunk_count": total,
                    "text": chunk,
                },
            )
            for index, total, chunk in self._select_chunks(attachment, text)
        ]
        return {
            **metadata,
            "chunked_summary": self._digest_evidence(self._reduce_digests(metadata, digests, reduce_system)),
        }

    def _select_message_body_chunks(self, body: str) -> tuple[list[tuple[int, int, str]], str | None]:
        """Возвращает фрагменты тела и предупреждение при равномерной выборке."""

        size = self.settings.limits.message_body_chunk_size
        source = [body[offset : offset + size] for offset in range(0, len(body), size)]
        total = len(source)
        maximum = self.settings.limits.max_message_body_summary_chunks
        if total <= maximum:
            indices = list(range(total))
            warning = None
        elif maximum == 1:
            indices = [0]
            warning = f"Тело письма состоит из {total} фрагментов; для суммаризации выбран 1 фрагмент."
        else:
            indices = sorted({round(index * (total - 1) / (maximum - 1)) for index in range(maximum)})
            warning = f"Тело письма состоит из {total} фрагментов; для суммаризации выбрано {len(indices)} из них."
        return [(index + 1, total, source[index]) for index in indices], warning

    def _chunked_message_body_summary(self, body: str) -> tuple[dict[str, Any], str | None]:
        chunks, sampling_warning = self._select_message_body_chunks(body)
        digests = [
            self._digest(
                MESSAGE_BODY_CHUNK_SYSTEM,
                {"chunk_number": index, "chunk_count": total, "text": chunk},
            )
            for index, total, chunk in chunks
        ]
        metadata = {"kind": "message_body", "chunk_count": chunks[0][1]}
        digest = self._reduce_digests(metadata, digests, MESSAGE_BODY_REDUCE_SYSTEM)
        if sampling_warning and sampling_warning not in digest.warnings_ru:
            digest.warnings_ru = [*digest.warnings_ru[:3], sampling_warning]
        return self._digest_evidence(digest), sampling_warning

    @staticmethod
    def _forwarded_sections(body: str) -> list[str]:
        """Сохраняет границы уровней пересылки перед поэтапной суммаризацией."""

        sections: list[str] = []
        current: list[str] = []
        for line in body.splitlines():
            if line.startswith("[Пересланное сообщение ") and current:
                sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current).strip())
        return [section for section in sections if section]

    def _summarize_forwarded_chain(self, body: str) -> dict[str, Any] | None:
        sections = self._forwarded_sections(body)
        if not sections:
            return None
        size = min(self.settings.limits.chunk_size, max(1_000, self.settings.llm.max_text_chars_per_request // 2))
        chunk_values = [
            (level, number, len(chunks), chunk)
            for level, section in enumerate(sections, 1)
            for chunks in [[section[offset : offset + size] for offset in range(0, len(section), size)]]
            for number, chunk in enumerate(chunks, 1)
        ]
        maximum = self.settings.limits.max_forwarded_summary_chunks
        if len(chunk_values) > maximum:
            if maximum == 1:
                selected_indices = [0]
            else:
                selected_indices = sorted(
                    {round(index * (len(chunk_values) - 1) / (maximum - 1)) for index in range(maximum)}
                )
            chunk_values = [chunk_values[index] for index in selected_indices]
        grouped: dict[int, list[AttachmentDigest]] = {}
        for level, number, total, chunk in chunk_values:
            grouped.setdefault(level, []).append(
                self._digest(
                    FORWARDED_MESSAGE_CHUNK_SYSTEM,
                    {
                        "chain_level": level,
                        "chunk_number": number,
                        "chunk_count": total,
                        "text": chunk,
                    },
                )
            )
        levels: list[AttachmentDigest] = []
        for level, digests in grouped.items():
            levels.append(
                self._reduce_digests(
                    {"kind": "forwarded_email_level", "chain_level": level},
                    digests,
                    FORWARDED_MESSAGE_REDUCE_SYSTEM,
                )
            )
        chain = self._reduce_digests(
            {"kind": "forwarded_email_chain", "chain_depth": len(levels)},
            levels,
            FORWARDED_MESSAGE_REDUCE_SYSTEM,
        )
        if len(chunk_values) < sum(max(1, (len(section) + size - 1) // size) for section in sections):
            warning = (
                "Цепочка пересылки превышает лимит анализа; "
                f"использовано {len(chunk_values)} равномерно выбранных фрагментов."
            )
            chain.warnings_ru = [*chain.warnings_ru[:3], warning]
        return self._digest_evidence(chain)

    def _summary_attachment(self, attachment: dict[str, Any], text_limit: int) -> dict[str, Any]:
        extracted = self._attachment_text(attachment)
        return {
            **self._attachment_metadata(attachment),
            "extracted_text": self._shorten(extracted, text_limit),
        }

    @staticmethod
    def _attachment_requires_manual_review(attachment: dict[str, Any]) -> bool:
        if attachment.get("status") == "skipped":
            return True
        warnings = attachment.get("warnings")
        return isinstance(warnings, list) and any(
            "не удалось корректно извлечь" in str(warning).casefold() for warning in warnings
        )

    def _with_attachment_notices(self, summary: FinalSummary, attachments: list[dict[str, Any]]) -> FinalSummary:
        """Гарантирует заметное предупреждение о вложении, которое не удалось разобрать."""

        result = summary.model_copy(deep=True)
        for attachment in attachments:
            if not self._attachment_requires_manual_review(attachment):
                continue
            filename = self._shorten(attachment.get("original_filename"), 160) or "Вложение без имени"
            notice = f"{filename}: не удалось корректно обработать файл; требуется ручная проверка."
            if notice not in result.attachment_summaries:
                result.attachment_summaries.append(notice)
            if notice not in result.warnings_ru:
                result.warnings_ru.append(notice)
        return result

    def _classify_compact(self, evidence: dict[str, Any]) -> EmailClassification:
        """Классифицирует итоговые доказательства, когда полная сводка недоступна."""

        try:
            return self.llm.structured(
                CLASSIFICATION_SYSTEM,
                json.dumps(evidence, ensure_ascii=False),
                EmailClassification,
                max_tokens=min(500, self.settings.llm.max_completion_tokens),
            )
        except PermanentError:
            return manual_review_classification()

    def _final_from_digest(self, digest: AttachmentDigest, warning: str, evidence: dict[str, Any]) -> FinalSummary:
        """Преобразует короткую валидную сводку в итог без копирования исходного письма."""

        return FinalSummary(
            summary_ru=digest.summary_ru,
            classification=self._classify_compact(evidence),
            key_facts_ru=digest.key_facts_ru,
            action_items_ru=digest.action_items_ru,
            deadlines=digest.deadlines,
            warnings_ru=[warning, *digest.warnings_ru],
            confidence=digest.confidence,
        )

    def _generate_final_summary(self, evidence: dict[str, Any]) -> FinalSummary:
        """Повторяет итоговую генерацию и затем пробует более короткий контракт сводки."""

        serialized = json.dumps(evidence, ensure_ascii=False)
        last_error: PermanentError | None = None
        for attempt in range(self.settings.llm.final_summary_attempts):
            system = SUMMARY_SYSTEM if attempt == 0 else SUMMARY_RECOVERY_SYSTEM
            try:
                return self.llm.structured(system, serialized, FinalSummary)
            except PermanentError as exc:
                last_error = exc
                log_event(
                    LOGGER,
                    "final_summary_generation_retry",
                    level=logging.WARNING,
                    component="analysis",
                    attempt=attempt + 1,
                    max_attempts=self.settings.llm.final_summary_attempts,
                    error_type=type(exc).__name__,
                )

        forwarded_chain = evidence.get("forwarded_chain")
        if isinstance(forwarded_chain, dict):
            try:
                digest = AttachmentDigest.model_validate(forwarded_chain)
            except Exception:
                digest = None
            if digest is not None and digest.confidence > 0:
                return self._final_from_digest(
                    digest,
                    "Итоговая сводка сформирована из поэтапной сводки пересланных сообщений.",
                    evidence,
                )

        message_evidence = {
            "subject": evidence.get("subject"),
            "sender": evidence.get("sender"),
            "date": evidence.get("date"),
            "body": evidence.get("body"),
            "attachments": [
                {
                    "filename": item.get("filename"),
                    "status": item.get("status"),
                    "warnings": item.get("warnings"),
                }
                for item in evidence.get("attachments", [])
                if isinstance(item, dict)
            ],
        }
        body_digest = evidence.get("body_digest")
        if isinstance(body_digest, dict):
            message_evidence["body_digest"] = body_digest
        for attempt in range(self.settings.llm.final_summary_attempts):
            try:
                digest = self.llm.structured(
                    MESSAGE_DIGEST_SYSTEM,
                    json.dumps(message_evidence, ensure_ascii=False),
                    AttachmentDigest,
                    max_tokens=min(600, self.settings.llm.max_completion_tokens),
                )
                return self._final_from_digest(
                    digest,
                    "Итоговая сводка сформирована в сокращённом режиме после повторных попыток.",
                    evidence,
                )
            except PermanentError as exc:
                last_error = exc
                log_event(
                    LOGGER,
                    "final_summary_recovery_retry",
                    level=logging.WARNING,
                    component="analysis",
                    attempt=attempt + 1,
                    max_attempts=self.settings.llm.final_summary_attempts,
                    error_type=type(exc).__name__,
                )
        if last_error is not None:
            raise last_error
        raise LLMResponseFormatError("Не удалось сформировать итоговую сводку.")

    def summarize(
        self, message: dict[str, Any], body: str, attachments: list[dict[str, Any]], warnings: list[str]
    ) -> FinalSummary:
        evidence_budget = max(1_000, self.settings.llm.max_text_chars_per_request - 2_000)
        body_budget = evidence_budget // 3
        attachment_budget = max(300, (evidence_budget - body_budget) // max(1, len(attachments)))
        attachment_evidence: list[dict[str, Any]] = []
        for item in attachments:
            if self._attachment_requires_manual_review(item):
                attachment_evidence.append(self._attachment_metadata(item))
                continue
            text = self._attachment_text(item)
            if self._is_spreadsheet(item) or len(text) > self.settings.limits.chunk_size:
                attachment_evidence.append(self._chunked_attachment_summary(item, text))
            else:
                attachment_evidence.append(self._summary_attachment(item, attachment_budget))
        forwarded_chain = self._summarize_forwarded_chain(body) if message.get("is_forwarded") else None
        body_digest: dict[str, Any] | None = None
        body_sampling_warning: str | None = None
        if forwarded_chain is None and len(body) > body_budget:
            body_digest, body_sampling_warning = self._chunked_message_body_summary(body)
        evidence = {
            "subject": self._shorten(message.get("subject"), 600),
            "sender": self._shorten(message.get("from"), 300),
            "date": self._shorten(message.get("date"), 100),
            "body": "" if forwarded_chain is not None or body_digest is not None else self._shorten(body, body_budget),
            "attachment_count": len(attachments),
            "attachments": attachment_evidence,
            "warnings": [self._shorten(item, 300) for item in [*warnings, body_sampling_warning] if item][:20],
        }
        if forwarded_chain is not None:
            evidence["forwarded_chain"] = forwarded_chain
        if body_digest is not None:
            evidence["body_digest"] = body_digest
        # Тело письма и извлечённый текст вложений — исходные данные, их нельзя
        # подставлять в ячейку вместо сводки. До ручной проверки выполняются
        # повторные попытки с более компактным контрактом.
        summary = self._generate_final_summary(evidence)
        forwarded_warnings = forwarded_chain.get("warnings_ru", []) if isinstance(forwarded_chain, dict) else []
        if isinstance(forwarded_warnings, list):
            missing = [str(item) for item in forwarded_warnings if str(item) not in summary.warnings_ru]
            if missing:
                summary = summary.model_copy(deep=True)
                summary.warnings_ru.extend(missing)
        if body_sampling_warning and body_sampling_warning not in summary.warnings_ru:
            summary = summary.model_copy(deep=True)
            summary.warnings_ru.append(body_sampling_warning)
        return self._with_attachment_notices(summary, attachments)

    @staticmethod
    def ocr_text(result: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
        if isinstance(result.get("text"), str):
            lines = [
                line
                for page in result.get("pages", [])
                if isinstance(page, dict)
                for line in page.get("lines", [])
                if isinstance(line, dict)
            ]
            confidences = [
                float(line["confidence"]) for line in lines if isinstance(line.get("confidence"), (int, float))
            ]
            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            return result["text"], confidence, {"pages": result.get("pages", [])}
        pages = result.get("pages", [])
        values = [
            element.get("text", "")
            for page in pages
            if isinstance(page, dict)
            for element in page.get("elements", [])
            if isinstance(element, dict)
        ]
        return (
            "\n".join(item for item in values if isinstance(item, str)),
            0.0,
            {"pages": pages, "markdown": result.get("markdown")},
        )
