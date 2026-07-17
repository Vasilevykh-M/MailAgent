from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from yandex_drive import (
    DiskResource,
    InvalidRemotePathError,
    LocalFileError,
    OAuthToken,
    TokenRefreshError,
    YandexDriveConfig,
    YandexDriveService,
)
from yandex_drive.exceptions import DownloadError


def make_token(access: str = "valid", refresh: str | None = "refresh", seconds: int = 3600) -> OAuthToken:
    return OAuthToken(access, refresh, datetime.now(UTC) + timedelta(seconds=seconds))


class Store:
    def __init__(self, token: OAuthToken | None = None) -> None:
        self.token = token
        self.saved: list[OAuthToken] = []

    def load(self) -> OAuthToken | None:
        return self.token

    def save(self, token: OAuthToken) -> None:
        self.token = token
        self.saved.append(token)


class OAuth:
    def __init__(self, *, refreshed: OAuthToken | None = None, fails: bool = False) -> None:
        self.refreshed, self.fails = refreshed, fails
        self.interactive = 0

    def refresh(self, value: str) -> OAuthToken:
        if self.fails:
            raise TokenRefreshError("rejected")
        assert self.refreshed is not None
        return self.refreshed

    def authorize_interactively(self) -> OAuthToken:
        self.interactive += 1
        return make_token("interactive", "new-refresh")


class Api:
    def __init__(self, *, chunks: list[bytes] | None = None, fail_stream: bool = False) -> None:
        self.calls: list[object] = []
        self.chunks = chunks if chunks is not None else [b"\x00data", b"\xff"]
        self.fail_stream = fail_stream

    def get_metadata(self, remote: str) -> DiskResource:
        self.calls.append(("metadata", remote))
        return DiskResource("disk:" + remote, remote.rsplit("/", 1)[-1], "file", size=4)

    def get_download_url(self, remote: str) -> str:
        self.calls.append(("download-url", remote))
        return "temporary"

    def download_bytes(self, url: str) -> bytes:
        self.calls.append(("download", url))
        return b"\x00binary\xff"

    def iter_download(self, url: str, size: int):
        self.calls.append(("stream", url, size))
        for chunk in self.chunks:
            yield chunk
        if self.fail_stream:
            raise DownloadError("interrupted")

    def get_upload_url(self, remote: str, overwrite: bool) -> tuple[str, str]:
        self.calls.append(("upload-url", remote, overwrite))
        return "upload-url", "PUT"

    def upload_stream(self, url: str, stream: object, *, method: str) -> None:
        self.calls.append(("upload", url, getattr(stream, "read")(), method))


def config() -> YandexDriveConfig:
    return YandexDriveConfig(client_id="id", client_secret="secret", download_chunk_size=3)


def test_authorize_stored_refresh_and_fallback() -> None:
    stored = Store(make_token("stored"))
    oauth = OAuth()
    assert YandexDriveService(config(), token_store=stored, oauth_client=oauth, api_client=Api()).authorize().access_token == "stored"
    expired = Store(make_token("old", "old-refresh", seconds=-10))
    refreshed = make_token("new", None)
    service = YandexDriveService(config(), token_store=expired, oauth_client=OAuth(refreshed=refreshed), api_client=Api())
    result = service.authorize()
    assert result.access_token == "new" and result.refresh_token == "old-refresh" and expired.saved
    fallback = OAuth(fails=True)
    assert YandexDriveService(config(), token_store=Store(make_token(seconds=-1)), oauth_client=fallback, api_client=Api()).authorize().access_token == "interactive"
    assert fallback.interactive == 1


def test_download_binary_atomic_overwrite_and_cleanup(tmp_path: Path) -> None:
    api = Api(chunks=[b"ab", b"", b"cd"])
    service = YandexDriveService(config(), token_store=Store(make_token()), oauth_client=OAuth(), api_client=api)
    assert service.download_file("/file-without-extension") == b"\x00binary\xff"
    destination = tmp_path / "nested" / "result"
    assert service.download_file_to("/file-without-extension", destination) == destination
    assert destination.read_bytes() == b"abcd"
    assert ("stream", "temporary", 3) in api.calls
    with pytest.raises(LocalFileError):
        service.download_file_to("/file", destination)
    service.download_file_to("/file", destination, overwrite=True)
    failing = YandexDriveService(config(), token_store=Store(make_token()), oauth_client=OAuth(), api_client=Api(fail_stream=True))
    stable = tmp_path / "stable"
    stable.write_bytes(b"old")
    with pytest.raises(DownloadError):
        failing.download_file_to("/file", stable, overwrite=True)
    assert stable.read_bytes() == b"old" and not list(tmp_path.glob(".*.tmp"))


def test_upload_files_bytes_and_validation(tmp_path: Path) -> None:
    source = tmp_path / "no-extension"
    source.write_bytes(b"\x00payload\xff")
    api = Api()
    service = YandexDriveService(config(), token_store=Store(make_token()), oauth_client=OAuth(), api_client=api)
    result = service.upload_file(source, "disk:/archive/data", overwrite=True)
    assert result.name == "data" and ("upload-url", "disk:/archive/data", True) in api.calls
    assert any(call[0] == "upload" and call[2] == b"\x00payload\xff" for call in api.calls)
    service.upload_bytes(memoryview(b""), "/empty")
    service.upload_bytes(bytearray(b"bytes"), "/bytes")
    with pytest.raises(LocalFileError):
        service.upload_bytes("not bytes", "/x")  # type: ignore[arg-type]
    with pytest.raises(LocalFileError):
        service.upload_file(tmp_path, "/x")
    with pytest.raises(LocalFileError):
        service.upload_file(tmp_path / "missing", "/x")
    with pytest.raises(InvalidRemotePathError):
        service.get_metadata("   ")
