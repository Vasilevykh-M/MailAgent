from __future__ import annotations

from datetime import datetime

import pytest

from yandex_drive import DiskResource
from yandex_drive.exceptions import InvalidResponseError


def test_file_resource_round_trip_ignores_unknown_fields() -> None:
    resource = DiskResource.from_dict({
        "path": "disk:/file.bin", "name": "file.bin", "type": "file", "size": 4,
        "mime_type": "application/octet-stream", "created": "2026-01-01T01:02:03+00:00",
        "modified": "2026-01-02T01:02:03Z", "unknown": "ignored",
    })
    assert resource.resource_type == "file" and isinstance(resource.created, datetime)
    assert resource.to_dict()["modified"] == "2026-01-02T01:02:03+00:00"


def test_directory_and_missing_required_fields() -> None:
    directory = DiskResource.from_dict({"path": "disk:/photos", "name": "photos", "type": "dir"})
    assert directory.size is None and directory.mime_type is None
    with pytest.raises(InvalidResponseError):
        DiskResource.from_dict({"path": "disk:/missing", "type": "file"})
    with pytest.raises(InvalidResponseError):
        DiskResource.from_dict({"path": "disk:/x", "name": "x", "type": "file", "size": "4"})
