"""Public data models returned by the Yandex Mail service."""

from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Any

from .utils import safe_save_bytes


_STANDARD_FLAGS = {"\\seen", "\\flagged", "\\answered", "\\draft", "\\deleted", "\\recent"}


def _flag_values(flags: set[str]) -> tuple[bool, bool, bool, bool, bool, bool, bool, set[str]]:
    lowered = {flag.lower() for flag in flags}
    return (
        "\\seen" in lowered,
        "\\seen" not in lowered,
        "\\flagged" in lowered,
        "\\answered" in lowered,
        "\\draft" in lowered,
        "\\deleted" in lowered,
        "\\recent" in lowered,
        {flag for flag in flags if flag.lower() not in _STANDARD_FLAGS},
    )


def _date_value(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass(slots=True)
class Attachment:
    """A decoded MIME attachment held as binary data."""

    filename: str
    content_type: str
    content_disposition: str | None
    content_id: str | None
    charset: str | None
    size_bytes: int
    data: bytes = field(repr=False)
    is_inline: bool = False

    def to_dict(self, include_data: bool = False) -> dict[str, Any]:
        """Return a JSON-safe representation; binary data is opt-in Base64."""

        result: dict[str, Any] = {
            "filename": self.filename,
            "content_type": self.content_type,
            "content_disposition": self.content_disposition,
            "content_id": self.content_id,
            "charset": self.charset,
            "size_bytes": self.size_bytes,
            "is_inline": self.is_inline,
        }
        if include_data:
            result["data"] = b64encode(self.data).decode("ascii")
        return result

    def save(self, path: str | Path, *, overwrite: bool = False) -> Path:
        """Safely save this attachment and return the created path.

        ``path`` is treated as the requested filename. Its parent is the output
        directory and any unsafe sender-provided part is stripped.
        """

        raw_path = str(path).replace("\\", "/")
        sender_path = self.filename.replace("\\", "/")
        pure_path = PurePosixPath(raw_path)
        # If a caller composes ``output / attachment.filename`` and the sender's
        # name includes ../, Path.parent would already point outside ``output``.
        # Keep only the prefix before the first traversal component as root.
        parts = pure_path.parts
        if sender_path.startswith("/") or re.match(r"^[A-Za-z]:/", sender_path):
            # ``Path(output_dir) / '/sender/path'`` discards output_dir before
            # this method sees it. Falling back to the current directory is
            # conservative: it is always safer than honoring a sender-selected
            # absolute destination.
            directory = Path(".")
        elif ".." in parts:
            safe_parts = parts[:parts.index("..")]
            if safe_parts and safe_parts[0] == "/":
                directory = Path("/").joinpath(*safe_parts[1:])
            else:
                directory = Path(*safe_parts) if safe_parts else Path(".")
        else:
            directory = Path(path).parent or Path(".")
        return safe_save_bytes(directory, pure_path.name or self.filename, self.data, overwrite=overwrite)


@dataclass(slots=True)
class MessageStatus:
    """Current server-side IMAP flags for one UID."""

    uid: str
    mailbox: str
    flags: set[str]
    is_read: bool = field(init=False)
    is_unread: bool = field(init=False)
    is_important: bool = field(init=False)
    is_answered: bool = field(init=False)
    is_draft: bool = field(init=False)
    is_deleted: bool = field(init=False)
    is_recent: bool = field(init=False)
    custom_flags: set[str] = field(init=False)

    def __post_init__(self) -> None:
        self.flags = set(self.flags)
        self.refresh_flags()

    def refresh_flags(self) -> None:
        """Recalculate convenience booleans after changing ``flags``."""

        (
            self.is_read,
            self.is_unread,
            self.is_important,
            self.is_answered,
            self.is_draft,
            self.is_deleted,
            self.is_recent,
            self.custom_flags,
        ) = _flag_values(self.flags)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe status representation."""

        return {
            "uid": self.uid, "mailbox": self.mailbox, "flags": sorted(self.flags),
            "is_read": self.is_read, "is_unread": self.is_unread,
            "is_important": self.is_important, "is_answered": self.is_answered,
            "is_draft": self.is_draft, "is_deleted": self.is_deleted,
            "is_recent": self.is_recent, "custom_flags": sorted(self.custom_flags),
        }


@dataclass(slots=True)
class MessageSummary:
    """Metadata fetched without downloading a complete MIME body."""

    uid: str
    mailbox: str
    sequence_number: int | None
    subject: str
    from_: str
    to: list[str]
    cc: list[str]
    date: datetime | None
    raw_date: str | None
    message_id: str | None
    size_bytes: int
    flags: set[str]
    has_attachments: bool = False
    attachment_count: int | None = None
    is_read: bool = field(init=False)
    is_unread: bool = field(init=False)
    is_important: bool = field(init=False)
    is_answered: bool = field(init=False)
    is_draft: bool = field(init=False)
    is_deleted: bool = field(init=False)
    is_recent: bool = field(init=False)

    def __post_init__(self) -> None:
        self.flags = set(self.flags)
        self.refresh_flags()

    def refresh_flags(self) -> None:
        values = _flag_values(self.flags)
        (
            self.is_read, self.is_unread, self.is_important, self.is_answered,
            self.is_draft, self.is_deleted, self.is_recent, _,
        ) = values

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe summary representation."""

        return {
            "uid": self.uid, "mailbox": self.mailbox, "sequence_number": self.sequence_number,
            "subject": self.subject, "from": self.from_, "to": self.to, "cc": self.cc,
            "date": _date_value(self.date), "raw_date": self.raw_date,
            "message_id": self.message_id, "size_bytes": self.size_bytes,
            "flags": sorted(self.flags), "is_read": self.is_read, "is_unread": self.is_unread,
            "is_important": self.is_important, "is_answered": self.is_answered,
            "is_draft": self.is_draft, "is_deleted": self.is_deleted, "is_recent": self.is_recent,
            "has_attachments": self.has_attachments, "attachment_count": self.attachment_count,
        }


@dataclass(slots=True)
class MailMessage:
    """A fully downloaded and decoded RFC 5322 message."""

    uid: str
    mailbox: str
    sequence_number: int | None
    subject: str
    from_: str
    to: list[str]
    cc: list[str]
    bcc: list[str]
    reply_to: list[str]
    date: datetime | None
    raw_date: str | None
    message_id: str | None
    in_reply_to: str | None
    references: list[str]
    headers: list[tuple[str, str]]
    flags: set[str]
    size_bytes: int
    text_plain: str | None
    text_html: str | None
    attachments: list[Attachment]
    raw_bytes: bytes = field(repr=False)
    is_read: bool = field(init=False)
    is_unread: bool = field(init=False)
    is_important: bool = field(init=False)
    is_answered: bool = field(init=False)
    is_draft: bool = field(init=False)
    is_deleted: bool = field(init=False)
    is_recent: bool = field(init=False)

    def __post_init__(self) -> None:
        self.flags = set(self.flags)
        self.refresh_flags()

    def refresh_flags(self) -> None:
        values = _flag_values(self.flags)
        (
            self.is_read, self.is_unread, self.is_important, self.is_answered,
            self.is_draft, self.is_deleted, self.is_recent, _,
        ) = values

    def to_dict(self, include_attachment_data: bool = False, include_raw: bool = False) -> dict[str, Any]:
        """Return a JSON-safe full-message representation.

        Attachments and the original source are deliberately excluded by default
        because they can be large and contain sensitive information.
        """

        result: dict[str, Any] = {
            "uid": self.uid, "mailbox": self.mailbox, "sequence_number": self.sequence_number,
            "subject": self.subject, "from": self.from_, "to": self.to, "cc": self.cc,
            "bcc": self.bcc, "reply_to": self.reply_to, "date": _date_value(self.date),
            "raw_date": self.raw_date, "message_id": self.message_id,
            "in_reply_to": self.in_reply_to, "references": self.references,
            "headers": [[key, value] for key, value in self.headers], "flags": sorted(self.flags),
            "is_read": self.is_read, "is_unread": self.is_unread,
            "is_important": self.is_important, "is_answered": self.is_answered,
            "is_draft": self.is_draft, "is_deleted": self.is_deleted, "is_recent": self.is_recent,
            "size_bytes": self.size_bytes, "text_plain": self.text_plain, "text_html": self.text_html,
            "attachments": [item.to_dict(include_attachment_data) for item in self.attachments],
        }
        if include_raw:
            result["raw_bytes"] = b64encode(self.raw_bytes).decode("ascii")
        return result

    def save_attachments(self, directory: str | Path, *, overwrite: bool = False) -> list[Path]:
        """Safely save all attachment bytes underneath ``directory``."""

        return [safe_save_bytes(directory, item.filename, item.data, overwrite=overwrite) for item in self.attachments]

    def save_eml(self, path: str | Path, *, overwrite: bool = True) -> Path:
        """Write the original RFC 5322 bytes to an ``.eml`` file."""

        target = Path(path).expanduser()
        return safe_save_bytes(target.parent or Path("."), target.name or "message.eml", self.raw_bytes, overwrite=overwrite)


@dataclass(slots=True)
class MessagePage:
    """A page of message metadata."""

    items: list[MessageSummary]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe page representation."""

        return {
            "items": [item.to_dict() for item in self.items], "total": self.total,
            "limit": self.limit, "offset": self.offset, "has_more": self.has_more,
            "next_offset": self.next_offset,
        }
