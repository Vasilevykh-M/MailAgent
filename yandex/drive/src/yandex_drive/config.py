"""Configuration loading and validation for the standalone Drive SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re

from dotenv import dotenv_values

from .exceptions import ConfigurationError


DEFAULT_REDIRECT_URI = "https://oauth.yandex.ru/verification_code"
DEFAULT_SCOPE = "cloud_api:disk.read,cloud_api:disk.write"
DEFAULT_TOKEN_FILE = ".drive_tokens.json"
DEFAULT_API_BASE_URL = "https://cloud-api.yandex.net/v1/disk"
DEFAULT_TIMEOUT = 30.0
DEFAULT_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
REQUIRED_SCOPES = frozenset({"cloud_api:disk.read", "cloud_api:disk.write"})


def normalize_scopes(value: str | tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Return ordered, unique OAuth scopes from commas and/or whitespace."""

    if isinstance(value, str):
        parts = re.split(r"[\s,]+", value.strip())
    elif isinstance(value, (tuple, list)) and all(isinstance(item, str) for item in value):
        parts = [part for item in value for part in re.split(r"[\s,]+", item.strip())]
    else:
        raise ConfigurationError("YANDEX_DRIVE_OAUTH_SCOPE must be a string or sequence of strings.")
    return tuple(dict.fromkeys(part for part in parts if part))


@dataclass(slots=True)
class YandexDriveConfig:
    """Settings used by the Yandex Drive OAuth and REST API clients.

    Direct construction is supported for application embedding.  Secrets never
    appear in the dataclass representation, which makes ordinary diagnostic
    logging safer.
    """

    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = DEFAULT_REDIRECT_URI
    oauth_scope: str | tuple[str, ...] | list[str] = DEFAULT_SCOPE
    token_file: Path | str = Path(DEFAULT_TOKEN_FILE)
    api_base_url: str = DEFAULT_API_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    download_chunk_size: int = DEFAULT_DOWNLOAD_CHUNK_SIZE

    def __post_init__(self) -> None:
        self.client_id = str(self.client_id).strip()
        self.client_secret = str(self.client_secret).strip()
        self.redirect_uri = str(self.redirect_uri).strip()
        self.api_base_url = str(self.api_base_url).strip().rstrip("/")
        self.token_file = Path(self.token_file).expanduser()
        try:
            self.timeout = float(self.timeout)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("YANDEX_DRIVE_TIMEOUT must be a number.") from exc
        try:
            # Reject 1.5 rather than quietly truncating it to 1.
            if isinstance(self.download_chunk_size, float) and not self.download_chunk_size.is_integer():
                raise ValueError
            self.download_chunk_size = int(self.download_chunk_size)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("YANDEX_DRIVE_DOWNLOAD_CHUNK_SIZE must be an integer.") from exc
        self.oauth_scope = ",".join(normalize_scopes(self.oauth_scope))

    @property
    def scopes(self) -> tuple[str, ...]:
        """Normalized, ordered scopes suitable for OAuth URL construction."""

        return normalize_scopes(self.oauth_scope)

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "YandexDriveConfig":
        """Load a dotenv file while allowing process environment overrides.

        For credentials the Drive-specific name takes precedence over the
        generic Yandex name. Relative token paths are anchored at the dotenv
        file, not the process working directory.
        """

        path = Path(env_file).expanduser()
        values = dotenv_values(path) if path.exists() else {}

        def lookup(*names: str, default: str = "") -> str:
            for source in (os.environ, values):
                for name in names:
                    raw = source.get(name)
                    if raw is not None and str(raw).strip():
                        return str(raw).strip()
            return default

        token_file = Path(lookup("YANDEX_DRIVE_TOKEN_FILE", default=DEFAULT_TOKEN_FILE))
        if not token_file.is_absolute():
            token_file = path.parent / token_file
        return cls(
            client_id=lookup("YANDEX_DRIVE_CLIENT_ID", "YANDEX_CLIENT_ID"),
            client_secret=lookup("YANDEX_DRIVE_CLIENT_SECRET", "YANDEX_CLIENT_SECRET"),
            redirect_uri=lookup("YANDEX_DRIVE_REDIRECT_URI", default=DEFAULT_REDIRECT_URI),
            oauth_scope=lookup("YANDEX_DRIVE_OAUTH_SCOPE", default=DEFAULT_SCOPE),
            token_file=token_file,
            api_base_url=lookup("YANDEX_DRIVE_API_BASE_URL", default=DEFAULT_API_BASE_URL),
            timeout=lookup("YANDEX_DRIVE_TIMEOUT", default=str(DEFAULT_TIMEOUT)),
            download_chunk_size=lookup(
                "YANDEX_DRIVE_DOWNLOAD_CHUNK_SIZE", default=str(DEFAULT_DOWNLOAD_CHUNK_SIZE)
            ),
        )

    def validate(self, *, require_oauth: bool = True) -> None:
        """Validate settings before authorization or a Disk API operation."""

        missing: list[str] = []
        if require_oauth and not self.client_id:
            missing.append("YANDEX_DRIVE_CLIENT_ID")
        if require_oauth and not self.client_secret:
            missing.append("YANDEX_DRIVE_CLIENT_SECRET")
        if missing:
            raise ConfigurationError("Missing required configuration: " + ", ".join(missing) + ".")
        if not self.redirect_uri:
            raise ConfigurationError("YANDEX_DRIVE_REDIRECT_URI must not be empty.")
        missing_scopes = REQUIRED_SCOPES.difference(self.scopes)
        if missing_scopes:
            raise ConfigurationError(
                "YANDEX_DRIVE_OAUTH_SCOPE must include " + ", ".join(sorted(missing_scopes)) + "."
            )
        if not self.api_base_url:
            raise ConfigurationError("YANDEX_DRIVE_API_BASE_URL must not be empty.")
        if self.timeout <= 0:
            raise ConfigurationError("YANDEX_DRIVE_TIMEOUT must be positive.")
        if self.download_chunk_size <= 0:
            raise ConfigurationError("YANDEX_DRIVE_DOWNLOAD_CHUNK_SIZE must be positive.")
