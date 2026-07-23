from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth.service import AuthenticationService
from app.config import AuthenticationConfigurationError, Settings
from app.errors import AuthenticationError
from app.main import create_app


@dataclass
class MemoryUser:
    id: uuid.UUID
    username: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class MemorySession:
    id: uuid.UUID
    user_id: uuid.UUID
    token_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class MemoryAuthTransaction:
    def __init__(self, repository: MemoryAuthRepository) -> None:
        self.repository = repository

    async def find_user(self, username: str, *, for_update: bool = False) -> MemoryUser | None:
        del for_update
        return self.repository.users.get(username)

    async def create_user_if_absent(self, *, username: str, password_hash: str, now: datetime) -> MemoryUser | None:
        if username in self.repository.users:
            return None
        user = MemoryUser(uuid.uuid4(), username, password_hash, True, now, now)
        self.repository.users[username] = user
        return user

    def create_session(
        self, *, user_id: uuid.UUID, token_hash: str, created_at: datetime, expires_at: datetime
    ) -> MemorySession:
        session = MemorySession(uuid.uuid4(), user_id, token_hash, created_at, expires_at)
        self.repository.sessions[token_hash] = session
        return session

    async def find_active_user_for_token(self, token_hash: str, now: datetime) -> MemoryUser | None:
        session = self.repository.sessions.get(token_hash)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            return None
        user = next(
            (candidate for candidate in self.repository.users.values() if candidate.id == session.user_id), None
        )
        return user if user is not None and user.is_active else None

    async def revoke_active_session(self, token_hash: str, now: datetime) -> MemoryUser | None:
        user = await self.find_active_user_for_token(token_hash, now)
        if user is None:
            return None
        self.repository.sessions[token_hash].revoked_at = now
        return user

    async def revoke_user_sessions(self, user_id: uuid.UUID, now: datetime) -> None:
        for session in self.repository.sessions.values():
            if session.user_id == user_id and session.revoked_at is None and session.expires_at > now:
                session.revoked_at = now

    async def cleanup_sessions(self, *, now: datetime, revoked_before: datetime) -> int:
        deleted = [
            token_hash
            for token_hash, session in self.repository.sessions.items()
            if session.expires_at <= now or (session.revoked_at is not None and session.revoked_at <= revoked_before)
        ]
        for token_hash in deleted:
            del self.repository.sessions[token_hash]
        return len(deleted)


class MemoryAuthRepository:
    def __init__(self) -> None:
        self.users: dict[str, MemoryUser] = {}
        self.sessions: dict[str, MemorySession] = {}

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[MemoryAuthTransaction]:
        yield MemoryAuthTransaction(self)


class FailingAuthRepository:
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[MemoryAuthTransaction]:
        raise RuntimeError("database unavailable")
        yield MemoryAuthTransaction(MemoryAuthRepository())


class ReadRepository:
    async def list_month(self, *args: object, **kwargs: object) -> list[object]:
        return []


class TestStorage:
    def ready(self) -> bool:
        return True


def settings(*, password: str = "correct-horse-battery-staple") -> Settings:
    return Settings(
        writer_api_key="writer",
        reader_api_key="reader",
        auth_admin_username="admin",
        auth_admin_password=SecretStr(password),
    )


@pytest.mark.parametrize(
    "values",
    [
        {"auth_admin_username": "admin"},
        {"auth_admin_password": SecretStr("correct-horse-battery-staple")},
        {"auth_admin_username": "", "auth_admin_password": SecretStr("correct-horse-battery-staple")},
        {"auth_admin_username": " admin", "auth_admin_password": SecretStr("correct-horse-battery-staple")},
        {"auth_admin_username": "adm\nin", "auth_admin_password": SecretStr("correct-horse-battery-staple")},
        {"auth_admin_username": "admin", "auth_admin_password": SecretStr("short")},
        {"auth_admin_username": "admin", "auth_admin_password": SecretStr(" " * 12)},
        {"auth_admin_username": "admin", "auth_admin_password": SecretStr("x" * 1_025)},
    ],
)
def test_authentication_configuration_rejects_incomplete_or_unsafe_values(values: dict[str, object]) -> None:
    with pytest.raises(AuthenticationConfigurationError) as error:
        Settings(**values)
    assert "correct-horse-battery-staple" not in str(error.value)


def test_authentication_configuration_allows_bootstrap_to_be_disabled() -> None:
    selected = Settings()
    assert selected.administrator_bootstrap_enabled is False


@pytest.mark.asyncio
async def test_bootstrap_is_idempotent_updates_password_and_revokes_sessions() -> None:
    repository = MemoryAuthRepository()
    service = AuthenticationService(repository, settings())

    first = await service.bootstrap_administrator()
    assert first is not None and first.created
    user = repository.users["admin"]
    assert user.is_active
    assert user.password_hash.startswith("$argon2id$")
    assert "correct-horse-battery-staple" not in user.password_hash
    original_hash = user.password_hash

    second = await service.bootstrap_administrator()
    assert second is not None and not second.created and not second.password_changed
    assert repository.users["admin"].password_hash == original_hash

    active_login = await service.login("admin", "correct-horse-battery-staple")
    updated = AuthenticationService(repository, settings(password="new-correct-horse-battery"))
    changed = await updated.bootstrap_administrator()
    assert changed is not None and changed.password_changed
    assert repository.users["admin"].password_hash != original_hash
    assert repository.sessions[hashlib.sha256(active_login.access_token.encode()).hexdigest()].revoked_at is not None
    with pytest.raises(AuthenticationError):
        await updated.login("admin", "correct-horse-battery-staple")
    assert (await updated.login("admin", "new-correct-horse-battery")).access_token


@pytest.mark.asyncio
async def test_bootstrap_reactivates_user_without_creating_duplicate() -> None:
    repository = MemoryAuthRepository()
    service = AuthenticationService(repository, settings())
    await service.bootstrap_administrator()
    repository.users["admin"].is_active = False

    outcome = await service.bootstrap_administrator()

    assert outcome is not None and outcome.reactivated
    assert repository.users["admin"].is_active
    assert len(repository.users) == 1


@pytest.mark.asyncio
async def test_concurrent_bootstrap_does_not_create_duplicate_user() -> None:
    repository = MemoryAuthRepository()
    first, second = AuthenticationService(repository, settings()), AuthenticationService(repository, settings())

    await asyncio.gather(first.bootstrap_administrator(), second.bootstrap_administrator())

    assert list(repository.users) == ["admin"]


@pytest.mark.asyncio
async def test_login_rejects_unknown_inactive_expired_and_revoked_sessions() -> None:
    repository = MemoryAuthRepository()
    service = AuthenticationService(repository, settings())
    await service.bootstrap_administrator()

    with pytest.raises(AuthenticationError):
        await service.login("missing", "correct-horse-battery-staple")
    repository.users["admin"].is_active = False
    with pytest.raises(AuthenticationError):
        await service.login("admin", "correct-horse-battery-staple")
    repository.users["admin"].is_active = True
    result = await service.login("admin", "correct-horse-battery-staple")
    token_hash = hashlib.sha256(result.access_token.encode()).hexdigest()
    repository.sessions[token_hash].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(AuthenticationError):
        await service.current_user(result.access_token)


@pytest.mark.asyncio
async def test_session_cleanup_removes_expired_and_old_revoked_only() -> None:
    repository = MemoryAuthRepository()
    service = AuthenticationService(repository, settings())
    await service.bootstrap_administrator()
    first = await service.login("admin", "correct-horse-battery-staple")
    second = await service.login("admin", "correct-horse-battery-staple")
    third = await service.login("admin", "correct-horse-battery-staple")
    first_hash = hashlib.sha256(first.access_token.encode()).hexdigest()
    second_hash = hashlib.sha256(second.access_token.encode()).hexdigest()
    third_hash = hashlib.sha256(third.access_token.encode()).hexdigest()
    now = datetime.now(UTC)
    repository.sessions[first_hash].expires_at = now - timedelta(seconds=1)
    repository.sessions[second_hash].revoked_at = now - timedelta(days=8)

    assert await service.cleanup_sessions() == 2
    assert first_hash not in repository.sessions
    assert second_hash not in repository.sessions
    assert third_hash in repository.sessions


def test_auth_http_contract_sessions_and_technical_keys() -> None:
    repository = MemoryAuthRepository()
    selected = settings()
    app = create_app(
        selected,
        repository=ReadRepository(),  # type: ignore[arg-type]
        storage=TestStorage(),  # type: ignore[arg-type]
        auth_repository=repository,  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/api/v1/emails?limit=1").status_code == 401
        assert client.get("/api/v1/emails?limit=1", headers={"X-API-Key": "reader"}).status_code == 200
        assert client.get("/api/v1/emails?limit=1", headers={"Authorization": "Bearer reader"}).status_code == 200
        assert client.get("/api/v1/emails?limit=1", headers={"X-API-Key": "invalid"}).status_code == 401
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct-horse-battery-staple"},
        )
        assert login.status_code == 200
        payload = login.json()
        assert payload["token_type"] == "bearer"
        assert payload["expires_in"] == 28_800
        token = payload["access_token"]
        assert "password" not in payload
        assert token not in repository.sessions
        assert hashlib.sha256(token.encode()).hexdigest() in repository.sessions
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/v1/auth/me", headers=headers).json()["username"] == "admin"
        assert client.get("/api/v1/emails?limit=1", headers=headers).status_code == 200
        assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer reader"}).status_code == 401
        assert client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer reader"}).status_code == 401
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        assert client.put("/api/v1/internal/emails/a", headers=headers).status_code == 401
        wrong_password = client.post("/api/v1/auth/login", json={"username": "admin", "password": "incorrect-password"})
        unknown_user = client.post("/api/v1/auth/login", json={"username": "missing", "password": "incorrect-password"})
        assert wrong_password.status_code == unknown_user.status_code == 401
        assert wrong_password.json()["error"] == unknown_user.json()["error"] == "unauthorized"


def test_bootstrap_failure_prevents_application_start_and_does_not_log_password(
    caplog: pytest.LogCaptureFixture,
) -> None:
    selected = settings()
    app = create_app(
        selected,
        repository=ReadRepository(),  # type: ignore[arg-type]
        storage=TestStorage(),  # type: ignore[arg-type]
        auth_repository=FailingAuthRepository(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        with TestClient(app):
            pass
    assert "correct-horse-battery-staple" not in caplog.text
