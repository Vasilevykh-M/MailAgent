"""Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import dotenv_values

from .exceptions import ConfigurationError


DEFAULT_REDIRECT_URI = "https://oauth.yandex.ru/verification_code"
DEFAULT_SCOPE = "mail:imap_full"
DEFAULT_IMAP_HOST = "imap.yandex.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_MAILBOX = "INBOX"
DEFAULT_TOKEN_FILE = ".tokens.json"


@dataclass(slots=True)
class YandexMailConfig:
    """Settings needed to authenticate and access a Yandex mailbox.

    Secrets are deliberately supplied at runtime, typically from ``.env``.  The
    object can be created with incomplete settings for diagnostics; call
    :meth:`validate` before a network operation.
    """

    client_id: str = ""
    client_secret: str = ""
    email: str = ""
    redirect_uri: str = DEFAULT_REDIRECT_URI
    oauth_scope: str = DEFAULT_SCOPE
    imap_host: str = DEFAULT_IMAP_HOST
    imap_port: int = DEFAULT_IMAP_PORT
    imap_mailbox: str = DEFAULT_MAILBOX
    token_file: Path | str = Path(DEFAULT_TOKEN_FILE)
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self.token_file = Path(self.token_file).expanduser()
        try:
            self.imap_port = int(self.imap_port)
            self.timeout = float(self.timeout)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("IMAP port and timeout must be numbers.") from exc

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "YandexMailConfig":
        """Load settings from an env file, falling back to environment variables.

        Relative ``YANDEX_TOKEN_FILE`` paths are resolved relative to the env
        file, which makes command-line use independent of the current directory.
        """

        path = Path(env_file).expanduser()
        file_values = dotenv_values(path) if path.exists() else {}

        def value(name: str, default: str = "") -> str:
            # An explicit process environment value wins, which is convenient in
            # CI and containers. dotenv_values does not mutate os.environ.
            raw = os.environ.get(name, file_values.get(name, default))
            return str(raw).strip() if raw is not None else default

        token_file = Path(value("YANDEX_TOKEN_FILE", DEFAULT_TOKEN_FILE))
        if not token_file.is_absolute():
            token_file = path.parent / token_file
        return cls(
            client_id=value("YANDEX_CLIENT_ID"),
            client_secret=value("YANDEX_CLIENT_SECRET"),
            email=value("YANDEX_EMAIL"),
            redirect_uri=value("YANDEX_REDIRECT_URI", DEFAULT_REDIRECT_URI),
            oauth_scope=value("YANDEX_OAUTH_SCOPE", DEFAULT_SCOPE),
            imap_host=value("YANDEX_IMAP_HOST", DEFAULT_IMAP_HOST),
            imap_port=value("YANDEX_IMAP_PORT", str(DEFAULT_IMAP_PORT)),
            imap_mailbox=value("YANDEX_IMAP_MAILBOX", DEFAULT_MAILBOX),
            token_file=token_file,
        )

    def validate(self, *, require_oauth: bool = True, require_email: bool = True) -> None:
        """Raise :class:`ConfigurationError` when required settings are invalid."""

        missing: list[str] = []
        if require_oauth:
            if not self.client_id:
                missing.append("YANDEX_CLIENT_ID")
            if not self.client_secret:
                missing.append("YANDEX_CLIENT_SECRET")
        if require_email and not self.email:
            missing.append("YANDEX_EMAIL")
        if missing:
            raise ConfigurationError("Missing required configuration: " + ", ".join(missing) + ".")
        if self.redirect_uri != DEFAULT_REDIRECT_URI:
            raise ConfigurationError(
                "YANDEX_REDIRECT_URI must be https://oauth.yandex.ru/verification_code."
            )
        if self.oauth_scope != DEFAULT_SCOPE:
            raise ConfigurationError("YANDEX_OAUTH_SCOPE must include mail:imap_full exactly.")
        if not self.imap_host:
            raise ConfigurationError("YANDEX_IMAP_HOST must not be empty.")
        if not (1 <= self.imap_port <= 65535):
            raise ConfigurationError("YANDEX_IMAP_PORT must be between 1 and 65535.")
        if self.timeout <= 0:
            raise ConfigurationError("Timeout must be positive.")
