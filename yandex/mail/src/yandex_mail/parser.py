"""RFC 5322/MIME parsing kept separate from IMAP transport."""

from __future__ import annotations

from datetime import datetime
from email import policy
from email.header import decode_header
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
import re

from .exceptions import MessageParseError
from .models import Attachment, MailMessage


def decode_header_value(value: str | None) -> str:
    """Decode RFC 2047 header text with robust charset fallbacks."""

    if not value:
        return ""
    parts: list[str] = []
    try:
        chunks = decode_header(value)
    except (ValueError, TypeError):
        return str(value)
    for part, charset in chunks:
        if isinstance(part, bytes):
            encoding = charset or "utf-8"
            try:
                parts.append(part.decode(encoding, errors="replace"))
            except (LookupError, UnicodeError):
                parts.append(part.decode("utf-8", errors="replace"))
        else:
            parts.append(part)
    return "".join(parts)


def decode_addresses(value: str | None) -> list[str]:
    """Return decoded mailbox strings from one address header."""

    decoded = decode_header_value(value)
    result: list[str] = []
    for name, address in getaddresses([decoded]):
        clean_name = decode_header_value(name).strip()
        clean_address = address.strip()
        if clean_name and clean_address:
            result.append(f"{clean_name} <{clean_address}>")
        elif clean_address:
            result.append(clean_address)
        elif clean_name:
            result.append(clean_name)
    return result


def parse_date(value: str | None) -> datetime | None:
    """Parse an RFC 5322 Date header, returning ``None`` for malformed input."""

    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _decode_payload(part: object) -> bytes:
    # EmailMessage provides this API, but retaining a defensive implementation
    # works with unusual messages created by tests or older policy objects.
    try:
        payload = part.get_payload(decode=True)  # type: ignore[attr-defined]
    except Exception:
        payload = None
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8", errors="replace")
    try:
        raw = part.get_payload()  # type: ignore[attr-defined]
    except Exception:
        return b""
    return raw.encode("utf-8", errors="replace") if isinstance(raw, str) else b""


def _decode_text(data: bytes, charset: str | None) -> str:
    encoding = charset or "utf-8"
    try:
        return data.decode(encoding, errors="replace")
    except (LookupError, UnicodeError):
        return data.decode("utf-8", errors="replace")


def _filename(part: object, index: int) -> str:
    try:
        value = part.get_filename()  # type: ignore[attr-defined]
    except Exception:
        value = None
    decoded = decode_header_value(str(value)) if value else ""
    return decoded or f"attachment_{index}"


def _is_attachment(part: object) -> bool:
    try:
        disposition = part.get_content_disposition()  # type: ignore[attr-defined]
        filename = part.get_filename()  # type: ignore[attr-defined]
        content_type = part.get_content_type()  # type: ignore[attr-defined]
    except Exception:
        return False
    return bool(filename) or disposition in {"attachment", "inline"} or content_type == "message/rfc822"


def parse_message(
    raw_bytes: bytes,
    *,
    uid: str,
    mailbox: str,
    sequence_number: int | None = None,
    flags: set[str] | None = None,
    size_bytes: int | None = None,
) -> MailMessage:
    """Parse one raw IMAP message, preserving duplicate headers and MIME parts."""

    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    except Exception as exc:
        raise MessageParseError("Could not parse the MIME message.") from exc
    try:
        # raw_items retains order and duplicate field names, unlike Message.items
        # under policies that can coalesce certain structured headers.
        headers = [(str(name), str(value)) for name, value in message.raw_items()]
        plain_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[Attachment] = []
        parts = message.walk() if message.is_multipart() else [message]
        attachment_index = 1
        for part in parts:
            if part.is_multipart():
                continue
            content_type = part.get_content_type().lower()
            disposition = part.get_content_disposition()
            charset = part.get_content_charset()
            payload = _decode_payload(part)
            if _is_attachment(part):
                content_id = part.get("Content-ID")
                attachments.append(
                    Attachment(
                        filename=_filename(part, attachment_index),
                        content_type=content_type,
                        content_disposition=disposition,
                        content_id=str(content_id) if content_id else None,
                        charset=charset,
                        size_bytes=len(payload),
                        data=payload,
                        is_inline=disposition == "inline",
                    )
                )
                attachment_index += 1
                continue
            if content_type == "text/plain":
                plain_parts.append(_decode_text(payload, charset))
            elif content_type == "text/html":
                html_parts.append(_decode_text(payload, charset))
        raw_date = message.get("Date")
        references_raw = decode_header_value(message.get("References"))
        references = re.findall(r"<[^>]+>", references_raw) or references_raw.split()
        from_addresses = decode_addresses(message.get("From"))
        return MailMessage(
            uid=str(uid), mailbox=mailbox, sequence_number=sequence_number,
            subject=decode_header_value(message.get("Subject")),
            from_=from_addresses[0] if from_addresses else "",
            to=decode_addresses(message.get("To")), cc=decode_addresses(message.get("Cc")),
            bcc=decode_addresses(message.get("Bcc")), reply_to=decode_addresses(message.get("Reply-To")),
            date=parse_date(raw_date), raw_date=raw_date, message_id=decode_header_value(message.get("Message-ID")) or None,
            in_reply_to=decode_header_value(message.get("In-Reply-To")) or None, references=references,
            headers=headers, flags=set(flags or set()), size_bytes=size_bytes if size_bytes is not None else len(raw_bytes),
            text_plain="\n".join(plain_parts) if plain_parts else None,
            text_html="\n".join(html_parts) if html_parts else None,
            attachments=attachments, raw_bytes=raw_bytes,
        )
    except MessageParseError:
        raise
    except Exception as exc:
        raise MessageParseError("Could not decode the MIME message.") from exc
