"""Command-line interface for :class:`yandex_mail.YandexMailService`."""

from __future__ import annotations

import argparse
from datetime import date
import json
import logging
from pathlib import Path
import sys
import traceback
from typing import Any, Callable

from .config import YandexMailConfig
from .exceptions import YandexMailError
from .models import MailMessage, MessageStatus, MessageSummary
from .service import YandexMailService
from .token_store import TokenStore
from .utils import format_size


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD format.") from exc


def _add_mailbox_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mailbox", default="INBOX", help="Mailbox to use (default: INBOX).")


def build_parser() -> argparse.ArgumentParser:
    """Build the public ``yandex-mail`` argument parser."""

    parser = argparse.ArgumentParser(prog="yandex-mail", description="Yandex Mail OAuth/IMAP client")
    parser.add_argument("--env", default=".env", help="Path to .env configuration (default: .env).")
    parser.add_argument("--verbose", action="store_true", help="Show informational logs.")
    parser.add_argument("--debug", action="store_true", help="Show debug logs and tracebacks on errors.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("diagnose", help="Show safe configuration and token-file diagnostics.")

    auth = commands.add_parser("auth", help="Authorize with Yandex OAuth in a browser.")
    auth.add_argument("--force", action="store_true", help="Always begin a new authorization flow.")

    listing = commands.add_parser("list", help="List messages without downloading complete MIME bodies.")
    _add_mailbox_argument(listing)
    listing.add_argument("--status", choices=("all", "read", "unread", "important", "not-important", "answered", "unanswered", "draft", "deleted", "recent"), default="all")
    status_flags = listing.add_mutually_exclusive_group()
    for flag, status in (("all", "all"), ("unread", "unread"), ("read", "read"), ("important", "important"),
                         ("not-important", "not-important"), ("answered", "answered"), ("unanswered", "unanswered"),
                         ("draft", "draft"), ("deleted", "deleted"), ("recent", "recent")):
        status_flags.add_argument(f"--{flag}", dest="status_shortcut", action="store_const", const=status, help=f"Shortcut for --status {status}.")
    listing.add_argument("--limit", type=int, default=50, help="Maximum messages to display (default: 50).")
    listing.add_argument("--offset", type=int, default=0, help="Zero-based result offset.")
    listing.add_argument("--no-limit", action="store_true", help="Stream every matching message.")
    listing.add_argument("--batch-size", type=int, default=200, help="UID FETCH batch size (default: 200).")
    listing.add_argument("--sort", choices=("date", "uid", "sender", "subject", "size"), default="date")
    order = listing.add_mutually_exclusive_group()
    order.add_argument("--ascending", action="store_true", help="Sort ascending.")
    order.add_argument("--descending", action="store_true", help="Sort descending (default).")
    listing.add_argument("--sender")
    listing.add_argument("--recipient")
    listing.add_argument("--subject")
    listing.add_argument("--text")
    listing.add_argument("--since", type=_parse_date)
    listing.add_argument("--before", type=_parse_date)
    attachment_filter = listing.add_mutually_exclusive_group()
    attachment_filter.add_argument("--has-attachments", dest="has_attachments", action="store_true")
    attachment_filter.add_argument("--no-attachments", dest="has_attachments", action="store_false")
    listing.set_defaults(has_attachments=None)
    listing.add_argument("--larger-than", type=int)
    listing.add_argument("--smaller-than", type=int)
    listing.add_argument("--before-uid")
    output = listing.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print JSON.")
    output.add_argument("--json-lines", action="store_true", help="Print one JSON object per line.")

    status = commands.add_parser("status", help="Get current server-side message flags.")
    status.add_argument("uids", nargs="+", help="One or more message UIDs.")
    _add_mailbox_argument(status)
    status.add_argument("--json", action="store_true")

    read = commands.add_parser("read", help="Read and parse one complete MIME message.")
    read.add_argument("uid")
    _add_mailbox_argument(read)
    read.add_argument("--peek", action="store_true", help="Do not change the read flag.")
    read.add_argument("--json", action="store_true")
    read.add_argument("--include-attachment-data", action="store_true")
    read.add_argument("--include-raw", action="store_true")
    read.add_argument("--attachments-dir")
    read.add_argument("--raw-file")

    attachments = commands.add_parser("attachments", help="Save all attachments without marking a message read.")
    attachments.add_argument("uid")
    attachments.add_argument("--output", required=True, help="Output directory.")
    _add_mailbox_argument(attachments)

    for command, help_text in (
        ("mark-read", "Mark messages as read."), ("mark-unread", "Mark messages as unread."),
        ("mark-important", "Mark messages as important."), ("mark-not-important", "Remove the important flag."),
    ):
        flags = commands.add_parser(command, help=help_text)
        flags.add_argument("uids", nargs="+", help="One or more message UIDs.")
        _add_mailbox_argument(flags)
        flags.add_argument("--json", action="store_true")
    return parser


def _configure_logging(verbose: bool, debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _diagnose(env_file: str) -> int:
    config = YandexMailConfig.from_env(env_file)
    store = TokenStore(config.token_file)
    token = None
    token_state = "not available"
    try:
        token = store.load()
        token_state = "available" if token else "not present"
    except YandexMailError:
        token_state = "invalid or unreadable"
    items = [
        (".env found", "yes" if Path(env_file).expanduser().exists() else "no"),
        ("Client ID configured", "yes" if bool(config.client_id) else "no"),
        ("Client Secret configured", "yes" if bool(config.client_secret) else "no"),
        ("Email", config.email or "not configured"),
        ("Redirect URI", config.redirect_uri), ("OAuth scope", config.oauth_scope),
        ("IMAP host", config.imap_host), ("IMAP port", str(config.imap_port)),
        ("Default mailbox", config.imap_mailbox), ("Token-file path", str(config.token_file)),
        ("Token file exists", "yes" if store.exists() else "no"),
        ("Token file", token_state), ("Access token present", "yes" if token else "no"),
        ("Refresh token present", "yes" if token else "no"),
        ("Access token expired", "yes" if token and token.is_expired() else "no" if token else "unknown"),
    ]
    width = max(len(label) for label, _ in items)
    for label, value in items:
        print(f"{label + ':':<{width + 1}} {value}")
    return 0


def _short(value: str, width: int) -> str:
    return value if len(value) <= width else value[:max(width - 1, 0)] + "…"


def _print_table(items: list[MessageSummary] | Any) -> None:
    columns = (("UID", 8), ("Date", 18), ("Status", 7), ("Important", 9), ("Answered", 8),
               ("Attachments", 11), ("Size", 8), ("Sender", 28), ("Subject", 34))
    print("  ".join(f"{name:<{width}}" for name, width in columns))
    for item in items:
        values = (
            item.uid, item.date.strftime("%Y-%m-%d %H:%M") if item.date else "-",
            "read" if item.is_read else "unread", "yes" if item.is_important else "no",
            "yes" if item.is_answered else "no", str(item.attachment_count or (1 if item.has_attachments else 0)),
            format_size(item.size_bytes), item.from_, item.subject,
        )
        print("  ".join(f"{_short(str(value), width):<{width}}" for value, (_, width) in zip(values, columns)))


def _print_status(status: MessageStatus) -> None:
    rows = (
        ("UID", status.uid), ("Mailbox", status.mailbox), ("Read", "yes" if status.is_read else "no"),
        ("Important", "yes" if status.is_important else "no"), ("Answered", "yes" if status.is_answered else "no"),
        ("Draft", "yes" if status.is_draft else "no"), ("Deleted", "yes" if status.is_deleted else "no"),
        ("Recent", "yes" if status.is_recent else "no"), ("Flags", " ".join(sorted(status.flags)) or "(none)"),
    )
    for label, value in rows:
        print(f"{label + ':':<14}{value}")


def _print_message(message: MailMessage) -> None:
    print(f"UID: {message.uid}")
    print(f"From: {message.from_}")
    print(f"To: {', '.join(message.to)}")
    print(f"Subject: {message.subject}")
    print(f"Date: {message.raw_date or '-'}")
    print(f"Status: {'read' if message.is_read else 'unread'}; {'important' if message.is_important else 'normal'}")
    print("\nPlain text:\n")
    if message.text_plain is not None:
        print(message.text_plain)
    elif message.text_html is not None:
        print("No plain-text body is available; HTML body follows:\n")
        print(message.text_html)
    else:
        print("This message has no readable text body.")
    print("\nAttachments:")
    if message.attachments:
        for attachment in message.attachments:
            print(f"- {attachment.filename} ({attachment.content_type}, {format_size(attachment.size_bytes)})")
    else:
        print("(none)")


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _list(service: YandexMailService, args: argparse.Namespace) -> int:
    if args.status_shortcut is not None:
        if args.status != "all" and args.status != args.status_shortcut:
            raise ValueError("--status conflicts with the supplied status shortcut.")
        status = args.status_shortcut
    else:
        status = args.status
    options = dict(
        sender=args.sender, recipient=args.recipient, subject=args.subject, text=args.text,
        since=args.since, before=args.before, has_attachments=args.has_attachments,
        larger_than=args.larger_than, smaller_than=args.smaller_than,
    )
    if args.no_limit:
        if args.before_uid:
            raise ValueError("--before-uid is only supported for paged list output.")
        iterator = service.iter_messages(args.mailbox, status, args.batch_size, **options)
        if args.json_lines:
            for item in iterator:
                print(json.dumps(item.to_dict(), ensure_ascii=False))
        elif args.json:
            _json([item.to_dict() for item in iterator])
        else:
            _print_table(iterator)
        return 0
    page = service.list_messages(
        mailbox=args.mailbox, status=status, limit=args.limit, offset=args.offset, sort_by=args.sort,
        descending=not args.ascending, before_uid=args.before_uid, batch_size=args.batch_size, **options,
    )
    if args.json or args.json_lines:
        if args.json_lines:
            for item in page.items:
                print(json.dumps(item.to_dict(), ensure_ascii=False))
        else:
            _json(page.to_dict())
    else:
        _print_table(page.items)
        print(f"\nShowing {len(page.items)} of {page.total} messages.")
    return 0


def _run(args: argparse.Namespace, service_factory: Callable[[str], YandexMailService]) -> int:
    if args.command == "diagnose":
        return _diagnose(args.env)
    service = service_factory(args.env)
    if args.command == "auth":
        service.authorize(force=args.force)
        print("Authorization completed.\nTokens saved.")
        return 0
    if args.command == "list":
        return _list(service, args)
    if args.command == "status":
        statuses = service.get_message_statuses(args.uids, mailbox=args.mailbox)
        if args.json:
            _json([item.to_dict() for item in statuses] if len(statuses) > 1 else statuses[0].to_dict())
        else:
            for index, item in enumerate(statuses):
                if index:
                    print()
                _print_status(item)
        return 0
    if args.command == "read":
        message = service.read_message(args.uid, mailbox=args.mailbox, mark_read=not args.peek,
                                       attachments_dir=args.attachments_dir, raw_file=args.raw_file)
        if args.json:
            _json(message.to_dict(args.include_attachment_data, args.include_raw))
        else:
            _print_message(message)
        return 0
    if args.command == "attachments":
        message = service.read_message(args.uid, mailbox=args.mailbox, mark_read=False)
        for path in message.save_attachments(args.output):
            print(path)
        return 0
    action = {
        "mark-read": service.mark_many_as_read, "mark-unread": service.mark_many_as_unread,
        "mark-important": service.mark_many_as_important, "mark-not-important": service.mark_many_as_not_important,
    }.get(args.command)
    if action:
        statuses = action(args.uids, mailbox=args.mailbox)
        if args.json:
            _json([item.to_dict() for item in statuses])
        else:
            for index, item in enumerate(statuses):
                if index:
                    print()
                _print_status(item)
        return 0
    raise ValueError("Unknown command.")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process-compatible exit status."""

    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose, args.debug)
    try:
        return _run(args, YandexMailService.from_env)
    except (YandexMailError, ValueError, OSError) as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
