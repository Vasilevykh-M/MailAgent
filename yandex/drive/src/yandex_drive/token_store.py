"""Safe, atomic persistence for standalone Yandex Drive OAuth tokens."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .exceptions import TokenStorageError


@dataclass(slots=True)
class OAuthToken:
    """OAuth credentials persisted with an absolute expiry time.

    Credential strings are deliberately omitted from ``repr``. The optional
    refresh token covers OAuth responses that do not issue one.
    """

    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    token_type: str = "Bearer"
    scope: tuple[str, ...] | None = None

    def is_expired(self, leeway_seconds: int = 60, *, now: datetime | None = None) -> bool:
        """Return whether the token should be refreshed before a request."""

        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        return expires_at <= current + timedelta(seconds=leeway_seconds)

    def to_dict(self) -> dict[str, object]:
        """Produce the JSON representation; callers must never log it."""

        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        result: dict[str, object] = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": expires_at.astimezone(UTC).isoformat(),
            "token_type": self.token_type,
        }
        if self.scope is not None:
            result["scope"] = list(self.scope)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OAuthToken":
        """Parse stored token data without including it in an exception."""

        try:
            access = value["access_token"]
            expires_at = datetime.fromisoformat(value["expires_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TokenStorageError("Token file has an invalid format.") from exc
        refresh = value.get("refresh_token")
        raw_scope = value.get("scope")
        if not isinstance(access, str) or not access or (refresh is not None and not isinstance(refresh, str)):
            raise TokenStorageError("Token file has an invalid format.")
        if raw_scope is None:
            scope = None
        elif isinstance(raw_scope, list) and all(isinstance(item, str) for item in raw_scope):
            scope = tuple(raw_scope)
        elif isinstance(raw_scope, str):
            scope = tuple(item for item in raw_scope.replace(",", " ").split() if item)
        else:
            raise TokenStorageError("Token file has an invalid format.")
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return cls(access, refresh, expires_at, str(value.get("token_type") or "Bearer"), scope)

    @classmethod
    def from_oauth_response(
        cls, value: Mapping[str, Any], *, now: datetime | None = None
    ) -> "OAuthToken":
        """Build a token from the safe, documented OAuth response fields."""

        access = value.get("access_token")
        refresh = value.get("refresh_token")
        if not isinstance(access, str) or not access or (refresh is not None and not isinstance(refresh, str)):
            raise TokenStorageError("OAuth response has an invalid token format.")
        try:
            expires_in = int(value.get("expires_in", 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        raw_scope = value.get("scope")
        if isinstance(raw_scope, str):
            scope = tuple(item for item in raw_scope.replace(",", " ").split() if item) or None
        elif isinstance(raw_scope, list) and all(isinstance(item, str) for item in raw_scope):
            scope = tuple(raw_scope) or None
        else:
            scope = None
        current = now or datetime.now(UTC)
        return cls(
            access_token=access,
            refresh_token=refresh,
            expires_at=current + timedelta(seconds=max(0, expires_in)),
            token_type=str(value.get("token_type") or "Bearer"),
            scope=scope,
        )


class TokenStore:
    """Read and atomically replace a Drive-only token file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> OAuthToken | None:
        """Return a stored token, ``None`` for an absent file, or a safe error."""

        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
            if not isinstance(value, dict):
                raise TokenStorageError("Token file has an invalid format.")
            return OAuthToken.from_dict(value)
        except TokenStorageError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise TokenStorageError("Could not read the token file safely.") from exc

    def save(self, token: OAuthToken) -> None:
        """Write credentials through a same-directory temporary file and replace."""

        temporary_name: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent, text=True
            )
            try:
                os.chmod(temporary_name, 0o600)
            except OSError:
                pass
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(token.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            temporary_name = None
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except OSError as exc:
            raise TokenStorageError("Could not save the token file safely.") from exc
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except OSError:
                    pass

    def clear(self) -> None:
        """Explicitly remove stored credentials."""

        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise TokenStorageError("Could not remove the token file.") from exc
