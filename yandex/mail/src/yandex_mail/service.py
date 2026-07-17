"""High-level reusable Yandex Mail library API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from email import policy
from email.parser import BytesParser
from typing import Callable, Generator, Iterable, Iterator
import re

from .config import YandexMailConfig
from .exceptions import (
    ConfigurationError,
    MessageFlagError,
    MessageNotFoundError,
    TokenRefreshError,
)
from .imap_client import FetchRecord, ImapClient
from .models import MailMessage, MessagePage, MessageStatus, MessageSummary
from .oauth import OAuthClient
from .parser import decode_addresses, decode_header_value, parse_date, parse_message
from .token_store import OAuthToken, TokenStore
from .utils import chunks


_STATUSES = {
    "all": (), "read": ("SEEN",), "unread": ("UNSEEN",),
    "important": ("FLAGGED",), "not-important": ("UNFLAGGED",),
    "answered": ("ANSWERED",), "unanswered": ("UNANSWERED",),
    "draft": ("DRAFT",), "deleted": ("DELETED",), "recent": ("RECENT",),
}
_SORT_FIELDS = {"date", "uid", "sender", "subject", "size"}
_KNOWN_SYSTEM_FLAGS = {"\\Seen", "\\Flagged", "\\Answered", "\\Draft", "\\Deleted", "\\Recent"}
_UID_SET_RE = re.compile(r"^\d+(?::\d+)?(?:,\d+(?::\d+)?)*$")
_KEYWORD_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _quoted(value: str) -> str:
    """Quote one IMAP SEARCH string argument without exposing it elsewhere."""

    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _imap_date(value: date | datetime) -> str:
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d-%b-%Y")


class YandexMailService:
    """OAuth-backed Yandex Mail operations for a terminal or Python application.

    The service is intentionally stateless with regard to IMAP connections:
    public operations open one connection, make batched requests, and clean it up.
    OAuth credentials remain in :class:`TokenStore`, never in module globals.
    """

    def __init__(
        self,
        config: YandexMailConfig,
        *,
        token_store: TokenStore | None = None,
        oauth_client: OAuthClient | None = None,
        imap_client_factory: Callable[[YandexMailConfig, Callable[[bool], str]], ImapClient] | None = None,
    ) -> None:
        self.config = config
        self.token_store = token_store or TokenStore(config.token_file)
        self.oauth_client = oauth_client or OAuthClient(config)
        self._imap_client_factory = imap_client_factory or (lambda cfg, provider: ImapClient(cfg, provider))

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "YandexMailService":
        """Create a service using an env file and process-environment overrides."""

        return cls(YandexMailConfig.from_env(env_file))

    def authorize(self, force: bool = False) -> OAuthToken:
        """Return usable tokens, refreshing or starting console OAuth as needed.

        ``force=True`` always launches a fresh Authorization Code Flow rather
        than using a stored credential.
        """

        self.config.validate()
        if not force:
            stored = self.token_store.load()
            if stored and not stored.is_expired():
                return stored
            if stored and stored.refresh_token:
                try:
                    refreshed = self.oauth_client.refresh(stored.refresh_token)
                    self.token_store.save(refreshed)
                    return refreshed
                except TokenRefreshError:
                    # The documented recovery path is a new interactive flow.
                    pass
        token = self.oauth_client.authorize_interactively()
        self.token_store.save(token)
        return token

    def get_access_token(self) -> str:
        """Return a valid access token, automatically refreshing it when needed."""

        return self._token_for_imap(False)

    def _token_for_imap(self, force_refresh: bool) -> str:
        self.config.validate()
        stored = self.token_store.load()
        if force_refresh and stored and stored.refresh_token:
            try:
                refreshed = self.oauth_client.refresh(stored.refresh_token)
            except TokenRefreshError:
                # A rejected refresh token requires a new interactive OAuth flow.
                return self.authorize(force=True).access_token
            self.token_store.save(refreshed)
            return refreshed.access_token
        if stored and not stored.is_expired():
            return stored.access_token
        return self.authorize().access_token

    @contextmanager
    def _mailbox(self, mailbox: str | None = None) -> Iterator[ImapClient]:
        self.config.validate()
        selected = mailbox or self.config.imap_mailbox
        client = self._imap_client_factory(self.config, self._token_for_imap)
        with client:
            client.select_mailbox(selected)
            yield client

    @staticmethod
    def _validate_status(status: str) -> str:
        if status not in _STATUSES:
            raise ConfigurationError("Unsupported status. Choose one of: " + ", ".join(_STATUSES) + ".")
        return status

    @staticmethod
    def _validate_uid(uid: str) -> str:
        if not isinstance(uid, str) or not uid.isdigit() or int(uid) <= 0:
            raise ValueError("Message UID must be a positive decimal number.")
        return uid

    @staticmethod
    def _validate_uid_set(uid_set: str) -> str:
        if not isinstance(uid_set, str) or not _UID_SET_RE.fullmatch(uid_set):
            raise ValueError("UID set must contain positive UIDs separated by commas or ranges.")
        return uid_set

    def _search_criteria(
        self,
        *, status: str, sender: str | None, recipient: str | None, subject: str | None,
        text: str | None, since: date | datetime | None, before: date | datetime | None,
        has_attachments: bool | None, larger_than: int | None, smaller_than: int | None,
    ) -> list[str]:
        criteria = list(_STATUSES[self._validate_status(status)])
        for label, value, keyword in (
            ("sender", sender, "FROM"), ("recipient", recipient, "TO"),
            ("subject", subject, "SUBJECT"), ("text", text, "TEXT"),
        ):
            if value is not None:
                if not value.strip():
                    raise ValueError(f"{label} filter must not be empty.")
                criteria.extend((keyword, _quoted(value)))
        if since is not None:
            if not isinstance(since, (date, datetime)):
                raise ValueError("since must be a date or datetime.")
            criteria.extend(("SINCE", _imap_date(since)))
        if before is not None:
            if not isinstance(before, (date, datetime)):
                raise ValueError("before must be a date or datetime.")
            criteria.extend(("BEFORE", _imap_date(before)))
        # IMAP has no universal "has attachment" search term. Content-Type is a
        # server-side header search and avoids downloading message bodies. It is
        # intentionally an efficient best-effort filter across IMAP servers.
        if has_attachments is True:
            criteria.extend(("HEADER", "Content-Type", _quoted("multipart")))
        if has_attachments is False:
            # A reliable negated attachment criterion is not portable. Do not
            # fetch bodies; server-side NOT header search is the closest option.
            criteria.extend(("NOT", "HEADER", "Content-Type", _quoted("multipart")))
        for label, value, keyword in (("larger_than", larger_than, "LARGER"), ("smaller_than", smaller_than, "SMALLER")):
            if value is not None:
                if not isinstance(value, int) or value < 0:
                    raise ValueError(f"{label} must be a non-negative integer.")
                criteria.extend((keyword, str(value)))
        return criteria

    def _find_uids(self, client: ImapClient, **filters: object) -> list[str]:
        criteria = self._search_criteria(**filters)  # type: ignore[arg-type]
        return client.search(criteria)

    @staticmethod
    def _summary_from_record(record: FetchRecord, mailbox: str) -> MessageSummary | None:
        if not record.uid:
            return None
        payload = record.payload or b""
        parsed = BytesParser(policy=policy.default).parsebytes(payload)
        raw_date = parsed.get("Date")
        from_values = decode_addresses(parsed.get("From"))
        content_type = (parsed.get("Content-Type") or "").lower()
        disposition = (parsed.get("Content-Disposition") or "").lower()
        # This intentionally does not claim an exact count without BODYSTRUCTURE.
        has_attachments = "multipart/mixed" in content_type or "attachment" in disposition or "name=" in content_type
        return MessageSummary(
            uid=record.uid, mailbox=mailbox, sequence_number=record.sequence_number,
            subject=decode_header_value(parsed.get("Subject")), from_=from_values[0] if from_values else "",
            to=decode_addresses(parsed.get("To")), cc=decode_addresses(parsed.get("Cc")),
            date=parse_date(raw_date), raw_date=raw_date,
            message_id=decode_header_value(parsed.get("Message-ID")) or None,
            size_bytes=record.size_bytes or 0, flags=record.flags,
            has_attachments=has_attachments, attachment_count=None,
        )

    def _fetch_summaries(self, client: ImapClient, uids: Iterable[str], mailbox: str, batch_size: int) -> Iterator[MessageSummary]:
        fields = "(UID FLAGS RFC822.SIZE INTERNALDATE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO CC DATE MESSAGE-ID CONTENT-TYPE CONTENT-DISPOSITION)])"
        for batch in chunks(uids, batch_size):
            records = client.fetch(",".join(batch), fields)
            for record in records:
                summary = self._summary_from_record(record, mailbox)
                if summary:
                    yield summary

    @staticmethod
    def _sort_summaries(items: list[MessageSummary], sort_by: str, descending: bool) -> None:
        if sort_by not in _SORT_FIELDS:
            raise ValueError("sort_by must be one of: " + ", ".join(sorted(_SORT_FIELDS)) + ".")
        if sort_by == "date":
            key = lambda item: item.date.timestamp() if item.date else float("-inf")
        elif sort_by == "uid":
            key = lambda item: int(item.uid)
        elif sort_by == "sender":
            key = lambda item: item.from_.casefold()
        elif sort_by == "subject":
            key = lambda item: item.subject.casefold()
        else:
            key = lambda item: item.size_bytes
        items.sort(key=key, reverse=descending)

    def list_messages(
        self,
        mailbox: str = "INBOX",
        status: str = "all",
        limit: int | None = 50,
        offset: int = 0,
        sort_by: str = "date",
        descending: bool = True,
        *,
        unread_only: bool | None = None,
        sender: str | None = None,
        recipient: str | None = None,
        subject: str | None = None,
        text: str | None = None,
        since: date | datetime | None = None,
        before: date | datetime | None = None,
        has_attachments: bool | None = None,
        larger_than: int | None = None,
        smaller_than: int | None = None,
        before_uid: str | None = None,
        batch_size: int = 200,
    ) -> MessagePage:
        """Return a filtered, metadata-only page using UID SEARCH and batched FETCH."""

        if unread_only is not None:
            translated = "unread" if unread_only else "all"
            if status != "all" and status != translated:
                raise ConfigurationError("status conflicts with unread_only.")
            status = translated
        self._validate_status(status)
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive or None.")
        if offset < 0:
            raise ValueError("offset must not be negative.")
        if before_uid is not None:
            self._validate_uid(before_uid)
        filters = dict(status=status, sender=sender, recipient=recipient, subject=subject, text=text,
                       since=since, before=before, has_attachments=has_attachments,
                       larger_than=larger_than, smaller_than=smaller_than)
        selected_mailbox = mailbox or self.config.imap_mailbox
        with self._mailbox(selected_mailbox) as client:
            uids = self._find_uids(client, **filters)
            if before_uid is not None:
                uids = [uid for uid in uids if int(uid) < int(before_uid)]
            # Metadata is fetched in batches, never complete MIME bodies.
            items = list(self._fetch_summaries(client, uids, selected_mailbox, batch_size))
        self._sort_summaries(items, sort_by, descending)
        total = len(items)
        page_items = items[offset:] if limit is None else items[offset:offset + limit]
        has_more = limit is not None and offset + len(page_items) < total
        return MessagePage(page_items, total, total if limit is None else limit, offset, has_more,
                           offset + len(page_items) if has_more else None)

    def iter_messages(
        self,
        mailbox: str = "INBOX",
        status: str = "all",
        batch_size: int = 200,
        **filters: object,
    ) -> Generator[MessageSummary, None, None]:
        """Yield matching metadata in batches without retaining all summaries."""

        self._validate_status(status)
        selected_mailbox = mailbox or self.config.imap_mailbox
        allowed = {"sender", "recipient", "subject", "text", "since", "before", "has_attachments", "larger_than", "smaller_than"}
        unexpected = set(filters) - allowed
        if unexpected:
            raise ValueError("Unsupported iterator filters: " + ", ".join(sorted(unexpected)) + ".")
        values = {name: filters.get(name) for name in allowed}
        with self._mailbox(selected_mailbox) as client:
            uids = self._find_uids(client, status=status, **values)
            # UID SEARCH generally returns ascending UIDs; reverse for the public
            # newest-first default while retaining only a batch of metadata.
            for summary in self._fetch_summaries(client, reversed(uids), selected_mailbox, batch_size):
                yield summary

    def get_all_messages(
        self, mailbox: str = "INBOX", status: str = "all", batch_size: int = 200, **filters: object
    ) -> list[MessageSummary]:
        """Retrieve all matching message summaries in efficient batches."""

        return list(self.iter_messages(mailbox, status, batch_size, **filters))

    def get_message_status(self, uid: str, mailbox: str = "INBOX", *, refresh: bool = True) -> MessageStatus:
        """Fetch current flags for one UID from the server."""

        self._validate_uid(uid)
        statuses = self.get_message_statuses([uid], mailbox=mailbox, refresh=refresh)
        if not statuses:
            raise MessageNotFoundError(f"Message UID {uid} was not found in {mailbox}.")
        return statuses[0]

    def get_message_statuses(
        self, uids: list[str] | tuple[str, ...] | str, mailbox: str = "INBOX", *, refresh: bool = True
    ) -> list[MessageStatus]:
        """Fetch current flags for multiple UIDs using a batched UID FETCH."""

        if isinstance(uids, str):
            uid_set = self._validate_uid_set(uids)
            requested: list[str] | None = uid_set.split(",") if ":" not in uid_set else None
        else:
            if not uids:
                return []
            requested = [self._validate_uid(uid) for uid in uids]
            uid_set = ",".join(requested)
        selected_mailbox = mailbox or self.config.imap_mailbox
        with self._mailbox(selected_mailbox) as client:
            records = client.fetch(uid_set, "(UID FLAGS)")
        found = [MessageStatus(record.uid, selected_mailbox, record.flags) for record in records if record.uid]
        by_uid = {status.uid: status for status in found}
        if requested is not None:
            missing = [uid for uid in requested if uid not in by_uid]
            if missing:
                raise MessageNotFoundError("Message UID was not found in " + selected_mailbox + ".")
            return [by_uid[uid] for uid in requested]
        if not found:
            raise MessageNotFoundError("No requested messages were found in " + selected_mailbox + ".")
        return found

    def read_message(
        self,
        uid: str,
        mailbox: str = "INBOX",
        mark_read: bool = True,
        attachments_dir: str | None = None,
        raw_file: str | None = None,
    ) -> MailMessage:
        """Fetch, MIME-parse, optionally save, and return one complete message."""

        self._validate_uid(uid)
        selected_mailbox = mailbox or self.config.imap_mailbox
        with self._mailbox(selected_mailbox) as client:
            # PEEK prevents implicit side effects; we explicitly add Seen below.
            records = client.fetch(uid, "(UID FLAGS RFC822.SIZE BODY.PEEK[])")
            record = next((item for item in records if item.uid == uid and item.payload is not None), None)
            if record is None:
                raise MessageNotFoundError(f"Message UID {uid} was not found in {selected_mailbox}.")
            message = parse_message(record.payload or b"", uid=uid, mailbox=selected_mailbox,
                                    sequence_number=record.sequence_number, flags=record.flags,
                                    size_bytes=record.size_bytes)
            if mark_read:
                client.store(uid, "+FLAGS.SILENT", {"\\Seen"})
            current_records = client.fetch(uid, "(UID FLAGS)")
            current = next((item for item in current_records if item.uid == uid), None)
            if current is None:
                raise MessageNotFoundError(f"Message UID {uid} disappeared while reading it.")
            message.flags = current.flags
            message.refresh_flags()
        if attachments_dir is not None:
            message.save_attachments(attachments_dir)
        if raw_file is not None:
            message.save_eml(raw_file)
        return message

    @staticmethod
    def _validate_flags(flags: set[str]) -> set[str]:
        normalized: set[str] = set()
        for flag in flags:
            if not isinstance(flag, str) or not flag:
                raise MessageFlagError("Flags must be non-empty strings.")
            canonical = next((value for value in _KNOWN_SYSTEM_FLAGS if value.lower() == flag.lower()), None)
            if canonical:
                normalized.add(canonical)
            elif flag.startswith("\\") or not _KEYWORD_RE.fullmatch(flag):
                raise MessageFlagError(f"Invalid IMAP flag: {flag!r}.")
            else:
                normalized.add(flag)
        return normalized

    def update_flags(
        self, uid: str, add: set[str] | None = None, remove: set[str] | None = None, mailbox: str = "INBOX"
    ) -> MessageStatus:
        """Add/remove flags, then fetch and return the server's current state."""

        self._validate_uid(uid)
        add_flags = self._validate_flags(set(add or set()))
        remove_flags = self._validate_flags(set(remove or set()))
        if {flag.lower() for flag in add_flags} & {flag.lower() for flag in remove_flags}:
            raise MessageFlagError("The same flag cannot be added and removed in one operation.")
        selected_mailbox = mailbox or self.config.imap_mailbox
        with self._mailbox(selected_mailbox) as client:
            if add_flags:
                client.store(uid, "+FLAGS.SILENT", add_flags)
            if remove_flags:
                client.store(uid, "-FLAGS.SILENT", remove_flags)
            records = client.fetch(uid, "(UID FLAGS)")
        record = next((item for item in records if item.uid == uid), None)
        if record is None:
            raise MessageNotFoundError(f"Message UID {uid} was not found in {selected_mailbox}.")
        return MessageStatus(uid, selected_mailbox, record.flags)

    def _update_many(self, uids: Iterable[str], *, add: set[str] | None = None, remove: set[str] | None = None,
                     mailbox: str = "INBOX") -> list[MessageStatus]:
        requested = [self._validate_uid(uid) for uid in uids]
        if not requested:
            return []
        add_flags = self._validate_flags(set(add or set()))
        remove_flags = self._validate_flags(set(remove or set()))
        if {flag.lower() for flag in add_flags} & {flag.lower() for flag in remove_flags}:
            raise MessageFlagError("The same flag cannot be added and removed in one operation.")
        selected_mailbox = mailbox or self.config.imap_mailbox
        with self._mailbox(selected_mailbox) as client:
            uid_set = ",".join(requested)
            if add_flags:
                client.store(uid_set, "+FLAGS.SILENT", add_flags)
            if remove_flags:
                client.store(uid_set, "-FLAGS.SILENT", remove_flags)
            records = client.fetch(uid_set, "(UID FLAGS)")
        found = {record.uid: MessageStatus(record.uid, selected_mailbox, record.flags) for record in records if record.uid}
        missing = [uid for uid in requested if uid not in found]
        if missing:
            raise MessageNotFoundError("One or more messages were not found after updating flags.")
        return [found[uid] for uid in requested]

    def mark_as_read(self, uid: str, mailbox: str = "INBOX") -> MessageStatus:
        """Set ``\\Seen`` and return the verified status."""

        return self.update_flags(uid, add={"\\Seen"}, mailbox=mailbox)

    def mark_as_unread(self, uid: str, mailbox: str = "INBOX") -> MessageStatus:
        """Remove ``\\Seen`` and return the verified status."""

        return self.update_flags(uid, remove={"\\Seen"}, mailbox=mailbox)

    def mark_as_important(self, uid: str, mailbox: str = "INBOX") -> MessageStatus:
        """Set ``\\Flagged`` and return the verified status."""

        return self.update_flags(uid, add={"\\Flagged"}, mailbox=mailbox)

    def mark_as_not_important(self, uid: str, mailbox: str = "INBOX") -> MessageStatus:
        """Remove ``\\Flagged`` and return the verified status."""

        return self.update_flags(uid, remove={"\\Flagged"}, mailbox=mailbox)

    def mark_many_as_read(self, uids: Iterable[str], mailbox: str = "INBOX") -> list[MessageStatus]:
        """Set ``\\Seen`` for several UIDs in one STORE request where possible."""

        return self._update_many(uids, add={"\\Seen"}, mailbox=mailbox)

    def mark_many_as_unread(self, uids: Iterable[str], mailbox: str = "INBOX") -> list[MessageStatus]:
        """Remove ``\\Seen`` for several UIDs."""

        return self._update_many(uids, remove={"\\Seen"}, mailbox=mailbox)

    def mark_many_as_important(self, uids: Iterable[str], mailbox: str = "INBOX") -> list[MessageStatus]:
        """Set ``\\Flagged`` for several UIDs."""

        return self._update_many(uids, add={"\\Flagged"}, mailbox=mailbox)

    def mark_many_as_not_important(self, uids: Iterable[str], mailbox: str = "INBOX") -> list[MessageStatus]:
        """Remove ``\\Flagged`` for several UIDs."""

        return self._update_many(uids, remove={"\\Flagged"}, mailbox=mailbox)
