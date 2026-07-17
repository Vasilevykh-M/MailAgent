"""Проверка ключей API в constant-time."""

from __future__ import annotations

import hmac
from collections.abc import Callable

from fastapi import Header

from .config import Settings, get_settings
from .errors import AuthenticationError


def _authenticated(provided: str | None, expected: str) -> bool:
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


def require_writer(settings: Settings | None = None) -> Callable[[str | None], None]:
    selected = settings or get_settings()

    def dependency(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if not _authenticated(x_api_key, selected.writer_api_key.get_secret_value()):
            raise AuthenticationError()

    return dependency


def require_reader(settings: Settings | None = None) -> Callable[[str | None], None]:
    selected = settings or get_settings()

    def dependency(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
    ) -> None:
        bearer = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None
        expected = selected.reader_api_key.get_secret_value()
        if not (_authenticated(x_api_key, expected) or _authenticated(bearer, expected)):
            raise AuthenticationError()

    return dependency
