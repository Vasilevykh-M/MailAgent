"""Адаптер публичного Yandex Disk SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast


class DriveGateway(Protocol):
    def metadata(self, remote_path: str) -> dict[str, Any]: ...

    def download(self, remote_path: str, destination: Path) -> Path: ...

    def upload(self, local_path: Path, remote_path: str, *, overwrite: bool) -> dict[str, Any]: ...

    def upload_bytes(self, data: bytes, remote_path: str, *, overwrite: bool) -> dict[str, Any]: ...


class YandexDriveAdapter:
    def __init__(self, env_file: Path) -> None:
        from yandex_drive import YandexDriveService

        self._service = YandexDriveService.from_env(str(env_file))

    @staticmethod
    def _resource(resource: Any) -> dict[str, Any]:
        return cast(dict[str, Any], resource.to_dict())

    def metadata(self, remote_path: str) -> dict[str, Any]:
        return self._resource(self._service.get_metadata(remote_path))

    def download(self, remote_path: str, destination: Path) -> Path:
        return Path(self._service.download_file_to(remote_path, destination, overwrite=True))

    def upload(self, local_path: Path, remote_path: str, *, overwrite: bool) -> dict[str, Any]:
        return self._resource(self._service.upload_file(local_path, remote_path, overwrite=overwrite))

    def upload_bytes(self, data: bytes, remote_path: str, *, overwrite: bool) -> dict[str, Any]:
        return self._resource(self._service.upload_bytes(data, remote_path, overwrite=overwrite))
