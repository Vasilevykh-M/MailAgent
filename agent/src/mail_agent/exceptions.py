"""Предметные ошибки с классификацией для ограниченных повторов."""

from __future__ import annotations


class MailAgentError(Exception):
    """Базовая ожидаемая ошибка агента."""


class RetryableError(MailAgentError):
    """Временная ошибка: письмо должно остаться непрочитанным."""


class PermanentError(MailAgentError):
    """Неисправимая без ручного вмешательства ошибка."""


class LLMResponseFormatError(PermanentError):
    """Модель вернула ответ, который не удалось привести к требуемой схеме."""


class ConfigurationError(PermanentError):
    """Конфигурация агента непригодна для безопасного запуска."""


class WorkbookConflictError(RetryableError):
    """Удалённая книга изменилась во время обновления."""


class WorkbookMissingError(PermanentError):
    """Требуемая удалённая книга отсутствует."""


class ExternalServiceError(RetryableError):
    """Временная недоступность Mail, Drive, LLM или OCR."""


class OCRServiceError(ExternalServiceError):
    """OCR-сервис недоступен или нарушил свой HTTP-контракт."""


class ResultsAPIError(ExternalServiceError):
    """Results API не подтвердил сохранение результата."""


class ResultsAPIPermanentError(PermanentError):
    """Results API отклонил данные как некорректные или конфликтные."""
