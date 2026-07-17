"""JSON-compatible models returned by the Yandex Disk API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from .exceptions import InvalidResponseError


def _parse_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidResponseError(f"Resource field {field_name!r} has an invalid format.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidResponseError(f"Resource field {field_name!r} has an invalid format.") from exc


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidResponseError(f"Resource field {field_name!r} has an invalid format.")
    return value


@dataclass(slots=True)
class DiskResource:
    """Metadata for either a file or a directory on Yandex Disk."""

    path: str
    name: str
    resource_type: str
    size: int | None = None
    mime_type: str | None = None
    media_type: str | None = None
    md5: str | None = None
    sha256: str | None = None
    created: datetime | None = None
    modified: datetime | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DiskResource":
        """Parse documented resource fields and safely ignore unknown keys."""

        if not isinstance(data, Mapping):
            raise InvalidResponseError("Resource metadata has an invalid format.")
        path = data.get("path")
        name = data.get("name")
        resource_type = data.get("type", data.get("resource_type"))
        if not isinstance(path, str) or not path or not isinstance(name, str) or not name:
            raise InvalidResponseError("Resource metadata is missing a required path or name.")
        if not isinstance(resource_type, str) or not resource_type:
            raise InvalidResponseError("Resource metadata is missing its resource type.")
        size = data.get("size")
        if size is not None and (isinstance(size, bool) or not isinstance(size, int)):
            raise InvalidResponseError("Resource field 'size' has an invalid format.")
        return cls(
            path=path,
            name=name,
            resource_type=resource_type,
            size=size,
            mime_type=_optional_string(data.get("mime_type"), "mime_type"),
            media_type=_optional_string(data.get("media_type"), "media_type"),
            md5=_optional_string(data.get("md5"), "md5"),
            sha256=_optional_string(data.get("sha256"), "sha256"),
            created=_parse_datetime(data.get("created"), "created"),
            modified=_parse_datetime(data.get("modified"), "modified"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible resource metadata."""

        return {
            "path": self.path,
            "name": self.name,
            "resource_type": self.resource_type,
            "size": self.size,
            "mime_type": self.mime_type,
            "media_type": self.media_type,
            "md5": self.md5,
            "sha256": self.sha256,
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
        }
