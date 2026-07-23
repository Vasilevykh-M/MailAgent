"""FastAPI dependencies, принимающие только пользовательские Bearer-сессии."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Header

from ..config import Settings
from ..errors import AuthenticationError
from .service import AuthenticatedUser, AuthenticationService


def bearer_token(authorization: str | None) -> str | None:
    if authorization is None or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:]
    return token if token else None


def _reader_key_token(token: str | None, settings: Settings) -> bool:
    expected = settings.reader_api_key.get_secret_value()
    return bool(token and expected and hmac.compare_digest(token.encode(), expected.encode()))


def require_current_user(
    settings: Settings, service: AuthenticationService | None
) -> Callable[[str | None], Awaitable[AuthenticatedUser]]:
    async def dependency(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
        token = bearer_token(authorization)
        if token is None or _reader_key_token(token, settings) or service is None:
            raise AuthenticationError()
        return await service.current_user(token)

    return dependency
