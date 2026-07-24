"""Адаптер Mail SDK без прямого IMAP-кода."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..models import MessageReference


class MailGateway(Protocol):
    def list_unread_all(self, mailbox: str, batch_size: int, *, unread_only: bool = True) -> list[MessageReference]: ...

    def fetch_message(self, uid: str, mailbox: str) -> dict[str, Any]: ...

    def mark_read(self, uid: str, mailbox: str) -> None: ...


class YandexMailAdapter:
    """Тонко преобразует публичные модели `yandex_mail` в JSON-совместимый вид."""

    def __init__(self, env_file: Path) -> None:
        from yandex_mail import YandexMailService

        self._service = YandexMailService.from_env(str(env_file))

    def list_unread_all(self, mailbox: str, batch_size: int, *, unread_only: bool = True) -> list[MessageReference]:
        result: list[MessageReference] = []
        offset = 0
        # Intentional page loop: batch_size never limits the total queue.
        while True:
            filters = {"status": "unread"} if unread_only else {}
            page = self._service.list_messages(
                mailbox=mailbox,
                limit=batch_size,
                offset=offset,
                sort_by="date",
                descending=False,
                batch_size=batch_size,
                **filters,
            )
            result.extend(
                MessageReference(
                    uid=item.uid,
                    mailbox=mailbox,
                    message_id=item.message_id,
                    date=item.date,
                    size_bytes=item.size_bytes,
                    flags=sorted(item.flags),
                )
                for item in page.items
            )
            if not page.has_more or page.next_offset is None:
                break
            offset = page.next_offset
        return result

    def fetch_message(self, uid: str, mailbox: str) -> dict[str, Any]:
        message = self._service.read_message(uid, mailbox=mailbox, mark_read=False)
        return {
            "uid": message.uid,
            "mailbox": message.mailbox,
            "message_id": message.message_id,
            "date": message.date.isoformat() if message.date else None,
            "subject": message.subject,
            "from": message.from_,
            "to": message.to,
            "cc": message.cc,
            "bcc": message.bcc,
            "reply_to": message.reply_to,
            "headers": [[name, value] for name, value in message.headers],
            "flags": sorted(message.flags),
            "custom_flags": sorted(
                flag
                for flag in message.flags
                if flag.lower() not in {"\\seen", "\\flagged", "\\answered", "\\draft", "\\deleted", "\\recent"}
            ),
            "is_read": message.is_read,
            "is_important": message.is_important,
            "is_answered": message.is_answered,
            "size_bytes": message.size_bytes,
            "text_plain": message.text_plain or "",
            "text_html": message.text_html or "",
            # Единственный путь к исходному MIME: graph немедленно переносит bytes во временный файл.
            "raw_bytes": message.raw_bytes,
            "attachments": [
                {
                    "filename": item.filename,
                    "content_type": item.content_type,
                    "content_id": item.content_id,
                    "is_inline": item.is_inline,
                    "size": item.size_bytes,
                    "data": item.data,
                }
                for item in message.attachments
            ],
        }

    def mark_read(self, uid: str, mailbox: str) -> None:
        self._service.mark_as_read(uid, mailbox=mailbox)
