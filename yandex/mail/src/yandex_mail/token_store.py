"""Secure local persistence for OAuth tokens."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .exceptions import TokenStorageError


@dataclass(slots=True)
class OAuthToken:
    """OAuth credentials with an absolute expiry time.

    The token strings are intentionally hidden from the normal dataclass repr so
    accidental logging does not expose credentials.
    """

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime
    token_type: str = "Bearer"

    def is_expired(self, leeway_seconds: int = 60) -> bool:
        """Return whether the access token should be refreshed before use."""

        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= datetime.now(UTC) + timedelta(seconds=leeway_seconds)

    def to_dict(self) -> dict[str, str]:
        """Create the on-disk JSON structure. Never use this for logging."""

        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": expires.astimezone(UTC).isoformat(),
            "token_type": self.token_type,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OAuthToken":
        """Parse a persisted token without including credential values in errors."""

        try:
            access = value["access_token"]
            refresh = value["refresh_token"]
            expires_at = datetime.fromisoformat(value["expires_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TokenStorageError("Token file has an invalid format.") from exc
        if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
            raise TokenStorageError("Token file has an invalid format.")
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return cls(access, refresh, expires_at, str(value.get("token_type") or "Bearer"))


class TokenStore:
    """Read and atomically write a local OAuth token file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    def exists(self) -> bool:
        """Whether a token file currently exists."""

        return self.path.exists()

    def load(self) -> OAuthToken | None:
        """Load saved credentials, or ``None`` when no file exists."""

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
        """Persist a token by replacing the final file atomically.

        The temporary file is in the same directory as the destination, so
        ``os.replace`` is atomic on supported local filesystems. POSIX modes are
        restricted before the replacement; Windows ignores chmod where needed.
        """

        temporary_name: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent, text=True
            )
            try:
                os.chmod(temporary_name, 0o600)
            except OSError:
                # Windows ACLs commonly control permissions and chmod can be a no-op.
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
            if temporary_name:
                try:
                    os.unlink(temporary_name)
                except OSError:
                    pass

    def clear(self) -> None:
        """Remove a stored token file when the caller explicitly requests it."""

        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise TokenStorageError("Could not remove the token file.") from exc
