from __future__ import annotations

import json
from pathlib import Path

from yandex_drive import DiskResource
from yandex_drive import cli
from yandex_drive.exceptions import LocalFileError


class Service:
    def __init__(self) -> None:
        self.auth_force: bool | None = None

    def authorize(self, force: bool = False) -> None:
        self.auth_force = force

    def get_metadata(self, path: str) -> DiskResource:
        return DiskResource(path, path.rsplit("/", 1)[-1], "dir")

    def download_file_to(self, remote: str, destination: str, *, overwrite: bool = False) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
        return path

    def upload_file(self, local: str, remote: str, *, overwrite: bool = False) -> DiskResource:
        return DiskResource(remote, remote.rsplit("/", 1)[-1], "file", size=4)


def test_help_diagnose_and_safe_json(capsys, tmp_path: Path) -> None:
    try:
        cli.main(["--help"])
    except SystemExit as error:
        assert error.code == 0
    assert cli.main(["--env", str(tmp_path / "missing.env"), "diagnose"]) == 0
    output = capsys.readouterr().out
    assert "Client Secret configured" in output and "your-client-secret" not in output


def test_auth_metadata_download_upload_and_expected_error(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    service = Service()
    monkeypatch.setattr(cli.YandexDriveService, "from_env", classmethod(lambda cls, path: service))
    assert cli.main(["auth", "--force"]) == 0 and service.auth_force is True
    capsys.readouterr()
    assert cli.main(["metadata", "/folder", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["resource_type"] == "dir"
    destination = tmp_path / "data"
    assert cli.main(["download", "/file-without-extension", "--output", str(destination), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["bytes_written"] == 4
    assert cli.main(["upload", str(destination), "/file.bin", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "file.bin"

    monkeypatch.setattr(
        cli.YandexDriveService,
        "from_env",
        classmethod(lambda cls, path: (_ for _ in ()).throw(LocalFileError("safe expected error"))),
    )
    assert cli.main(["metadata", "/x"]) == 1
    assert "safe expected error" in capsys.readouterr().err


def test_argument_error_is_status_two() -> None:
    try:
        cli.main(["download", "/x"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("argparse should reject missing --output")
