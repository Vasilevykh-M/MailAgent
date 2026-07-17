"""Проверка имени, сигнатуры и ограничений вложений."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..config import LimitsSettings
from ..models import AttachmentMeta

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"RIFF", "image/webp"),
    (b"PK\x03\x04", "application/zip"),
    (b"\xd0\xcf\x11\xe0", "application/x-ole-storage"),
)


def safe_filename(name: str, digest: str) -> str:
    candidate = _CONTROL.sub("_", name.replace("\\", "/").split("/")[-1]).strip(". ")
    candidate = candidate or "attachment"
    stem = Path(candidate).stem[:140] or "attachment"
    suffix = Path(candidate).suffix[:20]
    return f"{stem}-{digest[:12]}{suffix}"


def detect_content_type(data: bytes, declared: str, extension: str) -> str:
    for signature, content_type in _SIGNATURES:
        if data.startswith(signature):
            if content_type == "application/zip":
                return {
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                }.get(extension.lower(), content_type)
            if content_type == "application/x-ole-storage" and extension.lower() == ".xls":
                return "application/vnd.ms-excel"
            if content_type == "application/x-ole-storage" and extension.lower() == ".doc":
                return "application/msword"
            return content_type
    if extension.lower() in {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm"}:
        return declared or "text/plain"
    return declared or "application/octet-stream"


def build_metadata(item: dict[str, object], target_dir: Path, limits: LimitsSettings) -> AttachmentMeta:
    data = item.get("data")
    if not isinstance(data, bytes):
        raise ValueError("Attachment payload must be bytes.")
    digest = hashlib.sha256(data).hexdigest()
    original = str(item.get("filename") or "attachment")
    extension = Path(original).suffix.lower()
    raw_content_id = item.get("content_id")
    content_id = raw_content_id if isinstance(raw_content_id, str) else None
    if len(data) > limits.max_attachment_size:
        size = len(data)
        return AttachmentMeta(
            original_filename=original,
            safe_filename=safe_filename(original, digest),
            content_type=str(item.get("content_type") or ""),
            detected_content_type=detect_content_type(data[:32], str(item.get("content_type") or ""), extension),
            extension=extension,
            size=size,
            sha256=digest,
            is_inline=bool(item.get("is_inline")),
            content_id=content_id,
        )
    target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    safe = safe_filename(original, digest)
    path = target_dir / safe
    path.write_bytes(data)
    return AttachmentMeta(
        original_filename=original,
        safe_filename=safe,
        content_type=str(item.get("content_type") or ""),
        detected_content_type=detect_content_type(data[:32], str(item.get("content_type") or ""), extension),
        extension=extension,
        size=len(data),
        sha256=digest,
        is_inline=bool(item.get("is_inline")),
        content_id=content_id,
        file_path=str(path),
    )
