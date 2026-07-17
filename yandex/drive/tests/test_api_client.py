from __future__ import annotations

import io

import pytest
import requests

from yandex_drive import (
    AuthenticationError,
    PermissionDeniedError,
    ResourceNotFoundError,
    YandexDriveConfig,
)
from yandex_drive.api_client import YandexDriveApiClient
from yandex_drive.exceptions import DownloadError, InvalidResponseError, UploadError

from .conftest import FakeResponse, FakeSession


def client(session: FakeSession, token: dict[str, str] | None = None) -> tuple[YandexDriveApiClient, dict[str, int]]:
    token = token or {"value": "first-token"}
    refreshes = {"count": 0}

    def refresh() -> str:
        refreshes["count"] += 1
        token["value"] = "second-token"
        return token["value"]

    return YandexDriveApiClient(YandexDriveConfig(client_id="id", client_secret="secret"), lambda: token["value"], refresh, session=session), refreshes


def test_metadata_temporary_urls_and_binary_transfers() -> None:
    session = FakeSession([
        FakeResponse(body={"path": "disk:/folder", "name": "folder", "type": "dir"}),
        FakeResponse(body={"href": "https://signed/download"}),
        FakeResponse(content=b"\x00binary\xff"),
        FakeResponse(body={"href": "https://signed/upload", "method": "PUT"}),
        FakeResponse(status_code=201),
    ])
    api, _ = client(session)
    assert api.get_metadata("/folder").name == "folder"
    download_url = api.get_download_url("disk:/file-without-extension")
    assert api.download_bytes(download_url) == b"\x00binary\xff"
    upload_url, method = api.get_upload_url("/empty", True)
    api.upload_stream(upload_url, io.BytesIO(b""), method=method)
    main_call = session.calls[0][1]
    assert main_call["params"] == {"path": "/folder"}
    assert main_call["headers"]["Authorization"] == "OAuth first-token"
    assert "yandex-drive-sdk" in main_call["headers"]["User-Agent"]
    assert session.calls[1][1]["params"] == {"path": "disk:/file-without-extension"}
    assert session.calls[3][1]["params"] == {"path": "/empty", "overwrite": True}
    assert "Authorization" not in session.calls[2][1]["headers"]
    assert "Authorization" not in session.calls[4][1]["headers"]


def test_streaming_and_one_401_retry() -> None:
    streamed = FakeResponse(chunks=[b"one", b"", b"two"])
    session = FakeSession([
        FakeResponse(status_code=401),
        FakeResponse(body={"path": "disk:/x", "name": "x", "type": "file"}),
        streamed,
    ])
    api, refreshes = client(session)
    assert api.get_metadata("/x").path == "disk:/x"
    assert refreshes["count"] == 1 and len(session.calls) == 2
    assert session.calls[1][1]["headers"]["Authorization"] == "OAuth second-token"
    assert b"" not in list(api.iter_download("https://signed/download", 7))
    assert streamed.chunk_size == 7 and streamed.closed


def test_second_401_error_mapping_and_safe_failures() -> None:
    session = FakeSession([FakeResponse(status_code=401), FakeResponse(status_code=401)])
    api, refreshes = client(session)
    with pytest.raises(AuthenticationError):
        api.get_metadata("/x")
    assert refreshes["count"] == 1 and len(session.calls) == 2
    for status, expected in [(403, PermissionDeniedError), (404, ResourceNotFoundError)]:
        api, _ = client(FakeSession([FakeResponse(status_code=status)]))
        with pytest.raises(expected):
            api.get_metadata("/x")
    api, _ = client(FakeSession([FakeResponse(body={}, json_error=True)]))
    with pytest.raises(InvalidResponseError):
        api.get_metadata("/x")
    api, _ = client(FakeSession([FakeResponse(body={})]))
    with pytest.raises(InvalidResponseError) as error:
        api.get_download_url("/x")
    assert "signed" not in str(error.value) and "first-token" not in str(error.value)


def test_network_and_direct_transfer_errors() -> None:
    api, _ = client(FakeSession([requests.Timeout("timeout")]))
    with pytest.raises(Exception) as error:
        api.get_metadata("/x")
    assert "first-token" not in str(error.value)
    api, _ = client(FakeSession([FakeResponse(status_code=500)]))
    with pytest.raises(DownloadError):
        api.download_bytes("https://signed/download")
    api, _ = client(FakeSession([FakeResponse(status_code=500)]))
    with pytest.raises(UploadError):
        api.upload_stream("https://signed/upload", io.BytesIO(b"data"))
