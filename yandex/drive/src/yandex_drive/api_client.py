"""Low-level Yandex Disk REST and temporary-transfer HTTP client."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
import logging
from typing import Any, BinaryIO

import requests

from .config import YandexDriveConfig
from .exceptions import (
    AuthenticationError,
    DownloadError,
    DriveApiError,
    InvalidResponseError,
    PermissionDeniedError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    UploadError,
)
from .models import DiskResource


LOGGER = logging.getLogger(__name__)
USER_AGENT = "yandex-drive-sdk/0.1"


class YandexDriveApiClient:
    """Perform REST requests and transfer bytes without retaining OAuth state."""

    def __init__(
        self,
        config: YandexDriveConfig,
        access_token_provider: Callable[[], str],
        refresh_access_token: Callable[[], str],
        *,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self._access_token_provider = access_token_provider
        self._refresh_access_token = refresh_access_token
        self.session = session or requests.Session()

    def get_metadata(self, remote_path: str) -> DiskResource:
        """Retrieve metadata for a file or a directory."""

        return DiskResource.from_dict(self._json_main_request("GET", "/resources", {"path": remote_path}))

    def get_download_url(self, remote_path: str) -> str:
        """Ask the main API for a temporary download URL."""

        return self._href_from_response(
            self._json_main_request("GET", "/resources/download", {"path": remote_path})
        )

    def get_upload_url(self, remote_path: str, overwrite: bool) -> tuple[str, str]:
        """Ask the main API for a temporary upload URL and its HTTP method."""

        body = self._json_main_request(
            "GET", "/resources/upload", {"path": remote_path, "overwrite": overwrite}
        )
        href = self._href_from_response(body)
        method = body.get("method", "PUT")
        if not isinstance(method, str) or not method.strip():
            raise InvalidResponseError("Yandex Disk returned an invalid upload method.")
        return href, method.upper()

    def download_bytes(self, temporary_url: str) -> bytes:
        """Download a complete temporary-URL response into memory."""

        response = self._temporary_request("GET", temporary_url, transfer_error=DownloadError, stream=False)
        try:
            return bytes(response.content)
        except (AttributeError, TypeError) as exc:
            raise DownloadError("Yandex Disk returned an invalid download response.") from exc
        finally:
            self._close_response(response)

    def iter_download(self, temporary_url: str, chunk_size: int) -> Iterator[bytes]:
        """Yield non-empty byte chunks and always close the HTTP response."""

        response = self._temporary_request("GET", temporary_url, transfer_error=DownloadError, stream=True)
        try:
            try:
                chunks = response.iter_content(chunk_size=chunk_size)
                for chunk in chunks:
                    if chunk:
                        yield bytes(chunk)
            except requests.RequestException as exc:
                raise DownloadError("Yandex Disk download was interrupted.") from exc
            except (AttributeError, TypeError) as exc:
                raise DownloadError("Yandex Disk returned an invalid download stream.") from exc
        finally:
            self._close_response(response)

    def upload_stream(self, temporary_url: str, stream: BinaryIO, *, method: str = "PUT") -> None:
        """Upload a binary stream once; ambiguous transfer results are not retried."""

        response = self._temporary_request(
            method, temporary_url, transfer_error=UploadError, data=stream, stream=False
        )
        self._close_response(response)

    def _json_main_request(self, method: str, endpoint: str, params: Mapping[str, Any]) -> dict[str, Any]:
        response = self._main_request(method, endpoint, params=params)
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidResponseError("Yandex Disk returned an invalid JSON response.") from exc
        finally:
            self._close_response(response)
        if not isinstance(body, dict):
            raise InvalidResponseError("Yandex Disk returned an invalid JSON response.")
        return body

    def _main_request(
        self, method: str, endpoint: str, *, params: Mapping[str, Any]
    ) -> requests.Response:
        url = f"{self.config.api_base_url}{endpoint}"
        for attempt in range(2):
            try:
                token = self._access_token_provider()
                response = self.session.request(
                    method,
                    url,
                    params=dict(params),
                    headers={"Authorization": f"OAuth {token}", "User-Agent": USER_AGENT},
                    timeout=self.config.timeout,
                )
            except requests.RequestException as exc:
                raise DriveApiError("Could not contact the Yandex Disk API.") from exc
            status = self._status_code(response)
            if status == 401:
                self._close_response(response)
                if attempt == 0:
                    try:
                        self._refresh_access_token()
                    except AuthenticationError:
                        raise
                    except Exception as exc:
                        raise AuthenticationError("Could not refresh Yandex Disk credentials.") from exc
                    continue
                raise AuthenticationError("Yandex Disk rejected the access token after one refresh retry.")
            if not 200 <= status < 300:
                self._close_response(response)
                raise self._http_error(status)
            return response
        raise AuthenticationError("Yandex Disk rejected the access token after one refresh retry.")

    def _temporary_request(
        self,
        method: str,
        temporary_url: str,
        *,
        transfer_error: type[DriveApiError],
        data: BinaryIO | None = None,
        stream: bool,
    ) -> requests.Response:
        try:
            # No Authorization header is passed to signed temporary URLs.
            response = self.session.request(
                method, temporary_url, data=data, stream=stream, timeout=self.config.timeout,
                headers={"User-Agent": USER_AGENT},
            )
        except requests.RequestException as exc:
            raise transfer_error("Could not contact the Yandex Disk transfer service.") from exc
        status = self._status_code(response)
        if not 200 <= status < 300:
            self._close_response(response)
            raise transfer_error("Yandex Disk transfer was rejected.")
        return response

    @staticmethod
    def _href_from_response(body: Mapping[str, Any]) -> str:
        href = body.get("href")
        if not isinstance(href, str) or not href:
            raise InvalidResponseError("Yandex Disk did not return a transfer location.")
        return href

    @staticmethod
    def _status_code(response: object) -> int:
        status = getattr(response, "status_code", None)
        if not isinstance(status, int):
            raise InvalidResponseError("Yandex Disk returned an invalid HTTP response.")
        return status

    @staticmethod
    def _close_response(response: object) -> None:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _http_error(status: int) -> DriveApiError:
        if status == 403:
            return PermissionDeniedError("Yandex Disk denied access to this resource.")
        if status == 404:
            return ResourceNotFoundError("The Yandex Disk resource was not found.")
        if status == 409:
            return ResourceAlreadyExistsError("The Yandex Disk resource already exists.")
        return DriveApiError(f"Yandex Disk API request failed with HTTP status {status}.")
