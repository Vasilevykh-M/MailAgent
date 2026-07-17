"""Безопасные доменные ошибки, не раскрывающие данные писем."""

from __future__ import annotations


class APIError(Exception):
    status_code = 500
    code = "internal_error"
    retryable = False


class ValidationAPIError(APIError):
    status_code = 422
    code = "invalid_payload"


class AuthenticationError(APIError):
    status_code = 401
    code = "unauthorized"


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ConflictError(APIError):
    status_code = 409
    code = "generation_conflict"


class RetryableStorageError(APIError):
    status_code = 503
    code = "storage_unavailable"
    retryable = True
