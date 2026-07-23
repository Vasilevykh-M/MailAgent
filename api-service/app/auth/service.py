"""Доменная логика bootstrap, login и opaque-сессий без FastAPI-зависимостей."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..config import Settings
from ..errors import AuthenticationError
from .passwords import dummy_password_hash, hash_password, needs_rehash, verify_password
from .repository import AuthRepository
from .validation import PASSWORD_MAX_LENGTH, validate_password, validate_username


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    username: str


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    expires_in: int
    user: AuthenticatedUser


@dataclass(frozen=True)
class BootstrapResult:
    created: bool
    password_changed: bool
    reactivated: bool


class UserManagementError(ValueError):
    """Безопасная ошибка CLI для несуществующего или уже занятого пользователя."""


def _now() -> datetime:
    return datetime.now(UTC)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthenticationService:
    def __init__(self, repository: AuthRepository | Any, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def bootstrap_administrator(self) -> BootstrapResult | None:
        """Идемпотентно создаёт или синхронизирует configured администратора."""

        if not self.settings.administrator_bootstrap_enabled:
            return None
        username = self.settings.auth_admin_username
        password_secret = self.settings.auth_admin_password
        if username is None or password_secret is None:
            return None
        password = password_secret.get_secret_value()
        now = _now()
        created = password_changed = reactivated = False
        async with self.repository.transaction() as transaction:
            user = await transaction.find_user(username, for_update=True)
            if user is None:
                password_hash = await asyncio.to_thread(hash_password, password)
                user = await transaction.create_user_if_absent(
                    username=username,
                    password_hash=password_hash,
                    now=now,
                )
                if user is None:
                    user = await transaction.find_user(username, for_update=True)
                    if user is None:
                        raise RuntimeError("Authentication administrator bootstrap race could not be resolved")
                else:
                    created = True
            if not created and not await asyncio.to_thread(verify_password, user.password_hash, password):
                user.password_hash = await asyncio.to_thread(hash_password, password)
                password_changed = True
                await transaction.revoke_user_sessions(user.id, now)
            if not user.is_active:
                user.is_active = True
                reactivated = True
            if password_changed or reactivated:
                user.updated_at = now
        return BootstrapResult(created=created, password_changed=password_changed, reactivated=reactivated)

    async def login(self, username: str, password: str) -> LoginResult:
        """Создаёт server-side сессию только при валидной активной учётной записи."""

        try:
            validate_username(username)
            if len(password) > PASSWORD_MAX_LENGTH:
                raise ValueError("password is too long")
        except ValueError:
            await asyncio.to_thread(verify_password, dummy_password_hash(), password[:PASSWORD_MAX_LENGTH])
            raise AuthenticationError() from None
        now = _now()
        async with self.repository.transaction() as transaction:
            user = await transaction.find_user(username, for_update=True)
            password_matches = await asyncio.to_thread(
                verify_password,
                user.password_hash if user is not None else dummy_password_hash(),
                password,
            )
            if user is None or not user.is_active or not password_matches:
                raise AuthenticationError()
            if await asyncio.to_thread(needs_rehash, user.password_hash):
                user.password_hash = await asyncio.to_thread(hash_password, password)
                user.updated_at = now
            token = secrets.token_urlsafe(self.settings.auth_token_bytes)
            transaction.create_session(
                user_id=user.id,
                token_hash=_token_hash(token),
                created_at=now,
                expires_at=now + timedelta(seconds=self.settings.auth_session_ttl_seconds),
            )
            return LoginResult(
                access_token=token,
                expires_in=self.settings.auth_session_ttl_seconds,
                user=AuthenticatedUser(id=user.id, username=user.username),
            )

    async def current_user(self, token: str) -> AuthenticatedUser:
        now = _now()
        async with self.repository.transaction() as transaction:
            user = await transaction.find_active_user_for_token(_token_hash(token), now)
            if user is None:
                raise AuthenticationError()
            return AuthenticatedUser(id=user.id, username=user.username)

    async def logout(self, token: str) -> None:
        now = _now()
        async with self.repository.transaction() as transaction:
            user = await transaction.revoke_active_session(_token_hash(token), now)
            if user is None:
                raise AuthenticationError()

    async def cleanup_sessions(self, *, revoked_retention_seconds: int | None = None) -> int:
        retention = revoked_retention_seconds or self.settings.auth_revoked_session_retention_seconds
        if retention < 300:
            raise ValueError("revoked session retention must be at least 300 seconds")
        now = _now()
        async with self.repository.transaction() as transaction:
            return await transaction.cleanup_sessions(now=now, revoked_before=now - timedelta(seconds=retention))

    async def create_user(self, username: str, password: str) -> AuthenticatedUser:
        validate_username(username)
        validate_password(password)
        now = _now()
        password_hash = await asyncio.to_thread(hash_password, password)
        async with self.repository.transaction() as transaction:
            user = await transaction.create_user_if_absent(username=username, password_hash=password_hash, now=now)
            if user is None:
                raise UserManagementError("User already exists")
            return AuthenticatedUser(id=user.id, username=user.username)

    async def set_password(self, username: str, password: str) -> None:
        validate_username(username)
        validate_password(password)
        now = _now()
        async with self.repository.transaction() as transaction:
            user = await transaction.find_user(username, for_update=True)
            if user is None:
                raise UserManagementError("User was not found")
            user.password_hash = await asyncio.to_thread(hash_password, password)
            user.updated_at = now
            await transaction.revoke_user_sessions(user.id, now)

    async def set_active(self, username: str, is_active: bool) -> None:
        validate_username(username)
        now = _now()
        async with self.repository.transaction() as transaction:
            user = await transaction.find_user(username, for_update=True)
            if user is None:
                raise UserManagementError("User was not found")
            user.is_active = is_active
            user.updated_at = now
            if not is_active:
                await transaction.revoke_user_sessions(user.id, now)
