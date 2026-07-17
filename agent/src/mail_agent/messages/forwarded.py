"""Детерминированное выделение всех уровней распространённых пересылок."""

from __future__ import annotations

import re
from dataclasses import dataclass

_FORWARD_SEPARATOR = re.compile(
    r"""^
    \s*(?:[-_—–]{2,}\s*)?
    (?:
        forwarded\s+(?:message|email)
        |original\s+message
        |пересланное\s+сообщение
        |пересылаемое\s+сообщение
        |исходное\s+сообщение
        |начало\s+пересланного\s+сообщения
    )
    (?:\s*[-_—–]{2,})?\s*$
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)
_HEADER = re.compile(r"^\s*([^:\n]{1,40})\s*:\s*(.*?)\s*$")
_YANDEX_ENVELOPE = re.compile(
    r"""^\s*
    (?P<date>\d{1,2}\.\d{1,2}\.\d{4}\s*,\s*\d{1,2}:\d{2})
    \s*,\s*(?P<sender>.+?)\s*:\s*$
    """,
    re.VERBOSE,
)
_HEADER_NAMES = {
    "from": "from",
    "от": "from",
    "sender": "from",
    "date": "date",
    "дата": "date",
    "sent": "date",
    "отправлено": "date",
    "subject": "subject",
    "тема": "subject",
    "to": "to",
    "кому": "to",
    "cc": "cc",
    "копия": "cc",
    "bcc": "bcc",
    "скрытая копия": "bcc",
    "reply-to": "reply_to",
    "ответить": "reply_to",
}


@dataclass(frozen=True)
class ForwardedMessage:
    """Один уровень встроенного пересланного письма."""

    body: str
    forwarder_note: str | None = None
    sender: str | None = None
    date: str | None = None
    subject: str | None = None
    recipients: str | None = None


@dataclass(frozen=True)
class ForwardedChain:
    """Внешний комментарий и все уровни вложенной пересылки по порядку."""

    outer_note: str | None
    messages: tuple[ForwardedMessage, ...]


def _strip_disclaimer(value: str) -> str:
    """Убирает только типовые конфиденциальные footer-блоки, а не деловой текст."""

    lines = value.splitlines()
    for index in range(len(lines)):
        line = lines[index].casefold()
        english_notice = "intended solely" in line and ("recipient" in line or "business correspondence" in line)
        russian_notice = "конфиденциаль" in line and ("получател" in line or "удалите" in line)
        if english_notice or russian_notice:
            return "\n".join(lines[:index]).strip()
    return value.strip()


def _parse_forwarded_segment(value: str, forwarder_note: str | None = None) -> ForwardedMessage | None:
    lines = value.splitlines()
    headers: dict[str, str] = {}
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return None

    envelope = _YANDEX_ENVELOPE.match(lines[index])
    if envelope is not None:
        headers["date"] = envelope.group("date")
        headers["from"] = envelope.group("sender").strip()
        index += 1

    header_count = len(headers)
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            if header_count:
                index += 1
                break
            index += 1
            continue
        parsed = _HEADER.match(line)
        if parsed is None:
            break
        name, header_value = parsed.groups()
        normalized = _HEADER_NAMES.get(name.strip().casefold())
        if normalized is None:
            break
        if header_value.strip():
            headers[normalized] = header_value.strip()
        header_count += 1
        index += 1

    body = _strip_disclaimer("\n".join(lines[index:]))
    if not body and not headers:
        return None
    return ForwardedMessage(
        body=body,
        forwarder_note=forwarder_note,
        sender=headers.get("from"),
        date=headers.get("date"),
        subject=headers.get("subject"),
        recipients=headers.get("to"),
    )


def extract_forwarded_chain(value: str) -> ForwardedChain | None:
    """Выделяет все уровни пересылки, включая формат конверта Яндекс Почты."""

    separators = list(_FORWARD_SEPARATOR.finditer(value))
    if not separators:
        return None
    outer_note = value[: separators[0].start()].strip() or None
    messages: list[ForwardedMessage] = []
    for index, separator in enumerate(separators):
        end = separators[index + 1].start() if index + 1 < len(separators) else len(value)
        note = outer_note if index == 0 else None
        message = _parse_forwarded_segment(value[separator.end() : end], note)
        if message is not None:
            messages.append(message)
    return ForwardedChain(outer_note=outer_note, messages=tuple(messages)) if messages else None


def extract_forwarded_message(value: str) -> ForwardedMessage | None:
    """Совместимый доступ к первому уровню встроенной пересылки."""

    chain = extract_forwarded_chain(value)
    return chain.messages[0] if chain is not None else None


def format_forwarded_chain(chain: ForwardedChain) -> str:
    """Явно размечает все уровни цепочки для доказательной суммаризации."""

    parts: list[str] = []
    if chain.outer_note:
        parts.extend(["[Внешний комментарий переславшего]", chain.outer_note])
    for index, message in enumerate(chain.messages, 1):
        parts.append(f"[Пересланное сообщение {index}]")
        fields = [
            ("Отправитель", message.sender),
            ("Дата", message.date),
            ("Кому", message.recipients),
            ("Тема", message.subject),
        ]
        parts.extend(f"{label}: {value}" for label, value in fields if value)
        if message.body:
            parts.extend(["[Содержимое]", message.body])
    return "\n".join(parts).strip()
