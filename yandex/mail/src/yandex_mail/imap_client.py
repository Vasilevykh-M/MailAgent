"""Thin, testable IMAP XOAUTH2 transport wrapper."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
import imaplib
import logging
import re
import socket
from typing import Callable, Iterable

from .config import YandexMailConfig
from .exceptions import ImapAuthenticationError, ImapConnectionError, MailboxError, MessageFlagError


LOGGER = logging.getLogger(__name__)


def xoauth2_string(email: str, access_token: str) -> bytes:
    """Build the raw XOAUTH2 payload expected by ``imaplib.authenticate``.

    It is deliberately *not* Base64 encoded here: ``imaplib`` performs that
    encoding after invoking its authentication callback.
    """

    return f"user={email}\x01auth=Bearer {access_token}\x01\x01".encode("utf-8")


@dataclass(slots=True)
class FetchRecord:
    """One parsed ``UID FETCH`` response record."""

    uid: str | None
    sequence_number: int | None
    flags: set[str]
    size_bytes: int | None
    internaldate: str | None
    payload: bytes | None
    metadata: str


def parse_fetch_records(data: Iterable[object]) -> list[FetchRecord]:
    """Parse common imaplib FETCH response shapes without parsing MIME bodies."""

    records: list[FetchRecord] = []
    for item in data:
        # Flag-only FETCH responses are commonly plain bytes, while responses
        # containing a literal (headers/body) are ``(metadata, literal)`` tuples.
        if isinstance(item, (bytes, bytearray)):
            meta_raw, payload_raw = item, None
        elif isinstance(item, tuple) and item:
            meta_raw = item[0]
            payload_raw = item[1] if len(item) > 1 else None
        else:
            continue
        if not isinstance(meta_raw, (bytes, bytearray)):
            continue
        metadata = bytes(meta_raw).decode("utf-8", errors="replace")
        uid_match = re.search(r"\bUID\s+(\d+)", metadata, re.IGNORECASE)
        sequence_match = re.match(r"\s*(\d+)", metadata)
        flags_match = re.search(r"\bFLAGS\s+\(([^)]*)\)", metadata, re.IGNORECASE)
        size_match = re.search(r"\bRFC822\.SIZE\s+(\d+)", metadata, re.IGNORECASE)
        date_match = re.search(r'\bINTERNALDATE\s+"([^"]*)"', metadata, re.IGNORECASE)
        flags = set(flags_match.group(1).split()) if flags_match and flags_match.group(1).strip() else set()
        payload = bytes(payload_raw) if isinstance(payload_raw, (bytes, bytearray)) else None
        records.append(
            FetchRecord(
                uid=uid_match.group(1) if uid_match else None,
                sequence_number=int(sequence_match.group(1)) if sequence_match else None,
                flags=flags,
                size_bytes=int(size_match.group(1)) if size_match else None,
                internaldate=date_match.group(1) if date_match else None,
                payload=payload,
                metadata=metadata,
            )
        )
    return records


class ImapClient(AbstractContextManager["ImapClient"]):
    """An SSL IMAP connection authenticated with an automatically supplied token."""

    def __init__(
        self,
        config: YandexMailConfig,
        token_provider: Callable[[bool], str],
        *,
        imap_factory: Callable[..., imaplib.IMAP4_SSL] = imaplib.IMAP4_SSL,
    ) -> None:
        self.config = config
        self._token_provider = token_provider
        self._imap_factory = imap_factory
        self.connection: imaplib.IMAP4_SSL | None = None
        self.mailbox: str | None = None

    def __enter__(self) -> "ImapClient":
        return self.connect()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.logout()

    def connect(self) -> "ImapClient":
        """Open and authenticate; refresh and retry authentication once only."""

        if self.connection is not None:
            return self
        first_error: Exception | None = None
        for retry in (False, True):
            connection: imaplib.IMAP4_SSL | None = None
            try:
                token = self._token_provider(retry)
                connection = self._open_connection()
                # imaplib base64-encodes the callback return value. Never encode
                # ``xoauth2_string`` manually before passing it here.
                typ, _ = connection.authenticate("XOAUTH2", lambda _: xoauth2_string(self.config.email, token))
                if typ.upper() != "OK":
                    raise imaplib.IMAP4.error("XOAUTH2 authentication rejected")
                self.connection = connection
                return self
            except (imaplib.IMAP4.error, imaplib.IMAP4.abort, ImapConnectionError) as exc:
                first_error = exc
                if connection is not None:
                    try:
                        connection.logout()
                    except (imaplib.IMAP4.error, OSError):
                        pass
                self._discard_connection()
                if not retry:
                    continue
            except Exception as exc:
                # A token refresh error on the retry must be converted to an
                # authentication error without exposing credentials.
                first_error = exc
                if connection is not None:
                    try:
                        connection.logout()
                    except (imaplib.IMAP4.error, OSError):
                        pass
                self._discard_connection()
                if not retry:
                    continue
        raise ImapAuthenticationError("IMAP authentication failed after refreshing the access token.") from first_error

    def _open_connection(self) -> imaplib.IMAP4_SSL:
        try:
            return self._imap_factory(self.config.imap_host, self.config.imap_port, timeout=self.config.timeout)
        except (OSError, socket.timeout, imaplib.IMAP4.error) as exc:
            raise ImapConnectionError("Could not connect to the Yandex IMAP server.") from exc

    def select_mailbox(self, mailbox: str, *, readonly: bool = False) -> None:
        """Select a mailbox and raise a clear error on a server rejection."""

        connection = self._require_connection()
        try:
            typ, _ = connection.select(mailbox, readonly=readonly)
        except (imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError) as exc:
            raise MailboxError(f"Could not select mailbox {mailbox!r}.") from exc
        if typ.upper() != "OK":
            raise MailboxError(f"Could not select mailbox {mailbox!r}.")
        self.mailbox = mailbox

    def close_mailbox(self) -> None:
        """Close the selected writable mailbox, ignoring already-closed states."""

        if self.connection is None or self.mailbox is None:
            return
        try:
            typ, _ = self.connection.close()
            if typ.upper() not in {"OK", "NO", "BAD"}:
                raise MailboxError("Could not close the selected mailbox.")
        except imaplib.IMAP4.error as exc:
            raise MailboxError("Could not close the selected mailbox.") from exc
        finally:
            self.mailbox = None

    def logout(self) -> None:
        """Log out best-effort so cleanup never masks the original exception."""

        if self.connection is None:
            return
        connection = self.connection
        self.connection = None
        self.mailbox = None
        try:
            connection.logout()
        except (imaplib.IMAP4.error, OSError):
            LOGGER.debug("IMAP logout failed during cleanup.", exc_info=True)

    def search(self, criteria: list[str]) -> list[str]:
        """Run ``UID SEARCH`` and return UID strings."""

        connection = self._require_connection()
        try:
            typ, data = connection.uid("SEARCH", None, *criteria)
        except (imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError) as exc:
            raise ImapConnectionError("IMAP UID SEARCH failed.") from exc
        if typ.upper() != "OK":
            raise ImapConnectionError("IMAP UID SEARCH was rejected by the server.")
        if not data or not data[0]:
            return []
        raw = data[0].decode("ascii", errors="ignore") if isinstance(data[0], bytes) else str(data[0])
        return [value for value in raw.split() if value.isdigit()]

    def fetch(self, uid_set: str, fields: str) -> list[FetchRecord]:
        """Run a batched ``UID FETCH`` request."""

        connection = self._require_connection()
        try:
            typ, data = connection.uid("FETCH", uid_set, fields)
        except (imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError) as exc:
            raise ImapConnectionError("IMAP UID FETCH failed.") from exc
        if typ.upper() != "OK":
            raise ImapConnectionError("IMAP UID FETCH was rejected by the server.")
        return parse_fetch_records(data or [])

    def store(self, uid_set: str, operation: str, flags: set[str]) -> None:
        """Run one ``UID STORE`` request for the supplied UID set."""

        if not flags:
            return
        connection = self._require_connection()
        rendered_flags = "(" + " ".join(sorted(flags)) + ")"
        try:
            typ, _ = connection.uid("STORE", uid_set, operation, rendered_flags)
        except (imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError) as exc:
            raise MessageFlagError("IMAP UID STORE failed.") from exc
        if typ.upper() != "OK":
            raise MessageFlagError("IMAP UID STORE was rejected by the server.")

    def _require_connection(self) -> imaplib.IMAP4_SSL:
        if self.connection is None:
            raise ImapConnectionError("IMAP connection is not open.")
        return self.connection

    def _discard_connection(self) -> None:
        if self.connection is not None:
            self.logout()
