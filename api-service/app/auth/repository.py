"""Транзакционный репозиторий пользователей и серверных сессий."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import AuthSession, AuthUser


class AuthTransaction:
    """Операции auth внутри одной SQLAlchemy-транзакции."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_user(self, username: str, *, for_update: bool = False) -> AuthUser | None:
        statement = select(AuthUser).where(AuthUser.username == username)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def create_user_if_absent(
        self,
        *,
        username: str,
        password_hash: str,
        now: datetime,
    ) -> AuthUser | None:
        """Создаёт пользователя в savepoint, оставляя внешнюю транзакцию пригодной после race."""

        user = AuthUser(
            username=username,
            password_hash=password_hash,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(user)
                await self.session.flush()
        except IntegrityError:
            return None
        return user

    def create_session(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            created_at=created_at,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.session.add(session)
        return session

    async def find_active_user_for_token(self, token_hash: str, now: datetime) -> AuthUser | None:
        statement = (
            select(AuthUser)
            .join(AuthSession, AuthSession.user_id == AuthUser.id)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.expires_at > now,
                AuthSession.revoked_at.is_(None),
                AuthUser.is_active.is_(True),
            )
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def revoke_active_session(self, token_hash: str, now: datetime) -> AuthUser | None:
        statement = (
            select(AuthSession)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.expires_at > now,
                AuthSession.revoked_at.is_(None),
            )
            .with_for_update()
        )
        session = (await self.session.execute(statement)).scalar_one_or_none()
        if session is None:
            return None
        session.revoked_at = now
        user = await self.session.get(AuthUser, session.user_id)
        return user if user is not None and user.is_active else None

    async def revoke_user_sessions(self, user_id: uuid.UUID, now: datetime) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)
            .values(revoked_at=now)
        )

    async def cleanup_sessions(self, *, now: datetime, revoked_before: datetime) -> int:
        result = await self.session.execute(
            delete(AuthSession).where(
                or_(
                    AuthSession.expires_at <= now,
                    and_(AuthSession.revoked_at.is_not(None), AuthSession.revoked_at <= revoked_before),
                )
            )
        )
        return int(getattr(result, "rowcount", 0) or 0)


class AuthRepository:
    """Фабрика коротких транзакций поверх существующей session factory приложения."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AuthTransaction]:
        async with self.sessions() as session, session.begin():
            yield AuthTransaction(session)
