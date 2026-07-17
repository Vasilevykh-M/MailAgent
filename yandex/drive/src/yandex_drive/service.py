"""High-level reusable service for working with arbitrary Yandex Disk files."""

from __future__ import annotations

from collections.abc import Callable
import io
import logging
import os
from pathlib import Path
import tempfile

import requests

from .api_client import YandexDriveApiClient
from .config import YandexDriveConfig
from .exceptions import InvalidRemotePathError, LocalFileError, TokenRefreshError
from .models import DiskResource
from .oauth import OAuthClient
from .token_store import OAuthToken, TokenStore


LOGGER = logging.getLogger(__name__)


class YandexDriveService:
    """OAuth-backed Yandex Disk operations suitable for application embedding.

    This class has no CLI dependency and does not write to standard output. Its
    collaborators can be injected for deterministic tests, workers, and web
    applications.
    """

    def __init__(
        self,
        config: YandexDriveConfig,
        *,
        token_store: TokenStore | None = None,
        oauth_client: OAuthClient | None = None,
        api_client: YandexDriveApiClient | None = None,
        session: requests.Session | None = None,
        authorization_code_input: Callable[[str], str] = input,
        authorization_url_output: Callable[[str], None] = print,
    ) -> None:
        self.config = config
        self.token_store = token_store or TokenStore(config.token_file)
        self.oauth_client = oauth_client or OAuthClient(
            config,
            session=session,
            authorization_code_input=authorization_code_input,
            authorization_url_output=authorization_url_output,
        )
        self.api_client = api_client or YandexDriveApiClient(
            config,
            self.get_access_token,
            self._refresh_after_401,
            session=session,
        )

    @classmethod
    def from_env(cls, env_file: str | Path = ".env", **kwargs: object) -> "YandexDriveService":
        """Create a service using dotenv values and environment overrides."""

        return cls(YandexDriveConfig.from_env(env_file), **kwargs)

    def authorize(self, force: bool = False) -> OAuthToken:
        """Return a usable token, refreshing it or prompting only when needed."""

        self.config.validate()
        stored = None if force else self.token_store.load()
        if stored is not None and not stored.is_expired():
            return stored
        if stored is not None and stored.refresh_token:
            try:
                refreshed = self.oauth_client.refresh(stored.refresh_token)
                if not refreshed.refresh_token:
                    refreshed.refresh_token = stored.refresh_token
                self.token_store.save(refreshed)
                LOGGER.info("Yandex Disk OAuth token refreshed.")
                return refreshed
            except TokenRefreshError:
                # A rejected refresh token has one recovery path: a new code flow.
                LOGGER.info("Yandex Disk refresh token was rejected; starting interactive authorization.")
        token = self.oauth_client.authorize_interactively()
        self.token_store.save(token)
        LOGGER.info("Yandex Disk OAuth token saved.")
        return token

    def get_access_token(self) -> str:
        """Return the latest unexpired access token, refreshing as required."""

        self.config.validate()
        stored = self.token_store.load()
        if stored is not None and not stored.is_expired():
            return stored.access_token
        return self.authorize().access_token

    def get_metadata(self, remote_path: str) -> DiskResource:
        """Return file or directory metadata without downloading its contents."""

        self.config.validate()
        return self.api_client.get_metadata(self._validate_remote_path(remote_path))

    def download_file(self, remote_path: str) -> bytes:
        """Download a resource into memory; prefer :meth:`download_file_to` for large files."""

        self.config.validate()
        url = self.api_client.get_download_url(self._validate_remote_path(remote_path))
        return self.api_client.download_bytes(url)

    def download_file_to(
        self,
        remote_path: str,
        destination: str | Path,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Stream a resource to an atomically replaced local destination."""

        self.config.validate()
        remote_path = self._validate_remote_path(remote_path)
        target = Path(destination).expanduser()
        if target.exists() and not overwrite:
            raise LocalFileError("Destination already exists; pass overwrite=True to replace it.")
        if target.exists() and target.is_dir():
            raise LocalFileError("Destination must be a file path, not a directory.")
        temporary_name: str | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Request before creating the local temporary file, so failed URL
            # acquisition cannot leave a local artifact.
            url = self.api_client.get_download_url(remote_path)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            with os.fdopen(descriptor, "wb") as handle:
                for chunk in self.api_client.iter_download(url, self.config.download_chunk_size):
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
            temporary_name = None
            return target
        except LocalFileError:
            raise
        except OSError as exc:
            raise LocalFileError("Could not store the downloaded file safely.") from exc
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except OSError:
                    pass

    def upload_file(
        self, local_path: str | Path, remote_path: str, *, overwrite: bool = False
    ) -> DiskResource:
        """Stream one local regular file to Disk and return its resulting metadata."""

        self.config.validate()
        remote_path = self._validate_remote_path(remote_path)
        source = Path(local_path).expanduser()
        try:
            if not source.exists():
                raise LocalFileError("Local upload source does not exist.")
            if not source.is_file():
                raise LocalFileError("Local upload source must be a regular file.")
            url, method = self.api_client.get_upload_url(remote_path, overwrite)
            with source.open("rb") as handle:
                self.api_client.upload_stream(url, handle, method=method)
        except LocalFileError:
            raise
        except OSError as exc:
            raise LocalFileError("Could not read the local upload source.") from exc
        return self.api_client.get_metadata(remote_path)

    def upload_bytes(
        self, data: bytes | bytearray | memoryview, remote_path: str, *, overwrite: bool = False
    ) -> DiskResource:
        """Upload arbitrary bytes-like content without creating a local temporary file."""

        self.config.validate()
        remote_path = self._validate_remote_path(remote_path)
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise LocalFileError("upload_bytes requires bytes, bytearray, or memoryview data.")
        url, method = self.api_client.get_upload_url(remote_path, overwrite)
        with io.BytesIO(bytes(data)) as stream:
            self.api_client.upload_stream(url, stream, method=method)
        return self.api_client.get_metadata(remote_path)

    def _refresh_after_401(self) -> str:
        """Refresh/reacquire a token for the API client's single 401 retry."""

        self.config.validate()
        stored = self.token_store.load()
        if stored is not None and stored.refresh_token:
            try:
                refreshed = self.oauth_client.refresh(stored.refresh_token)
                if not refreshed.refresh_token:
                    refreshed.refresh_token = stored.refresh_token
                self.token_store.save(refreshed)
                LOGGER.info("Yandex Disk token refreshed after authentication rejection.")
                return refreshed.access_token
            except TokenRefreshError:
                pass
        return self.authorize(force=True).access_token

    @staticmethod
    def _validate_remote_path(remote_path: str) -> str:
        if not isinstance(remote_path, str) or not remote_path or not remote_path.strip():
            raise InvalidRemotePathError("Remote path must be a non-empty string.")
        return remote_path
