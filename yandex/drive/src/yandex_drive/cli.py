"""Thin command-line wrapper around :class:`YandexDriveService`."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import traceback
from typing import Callable

from .config import YandexDriveConfig
from .exceptions import YandexDriveError
from .models import DiskResource
from .service import YandexDriveService
from .token_store import TokenStore


def build_parser() -> argparse.ArgumentParser:
    """Build the public ``yandex-drive`` argument parser."""

    parser = argparse.ArgumentParser(prog="yandex-drive", description="Yandex Disk OAuth and REST API client")
    parser.add_argument("--env", default=".env", help="Path to .env configuration (default: .env).")
    parser.add_argument("--verbose", action="store_true", help="Show informational logs on stderr.")
    parser.add_argument("--debug", action="store_true", help="Show debug logs and tracebacks on errors.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("diagnose", help="Show safe configuration and token-file diagnostics.")
    auth = commands.add_parser("auth", help="Authorize with Yandex OAuth.")
    auth.add_argument("--force", action="store_true", help="Always start a new authorization-code flow.")

    metadata = commands.add_parser("metadata", help="Get file or directory metadata.")
    metadata.add_argument("remote_path")
    metadata.add_argument("--json", action="store_true", help="Print JSON only.")

    download = commands.add_parser("download", help="Stream a Yandex Disk file to a local path.")
    download.add_argument("remote_path")
    download.add_argument("--output", required=True, help="Destination file path.")
    download.add_argument("--overwrite", action="store_true", help="Replace an existing destination file.")
    download.add_argument("--json", action="store_true", help="Print JSON only.")

    upload = commands.add_parser("upload", help="Upload one local regular file.")
    upload.add_argument("local_path")
    upload.add_argument("remote_path")
    upload.add_argument("--overwrite", action="store_true", help="Replace an existing remote resource.")
    upload.add_argument("--json", action="store_true", help="Print JSON only.")
    return parser


def _configure_logging(verbose: bool, debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _diagnose(env_file: str) -> int:
    config = YandexDriveConfig.from_env(env_file)
    store = TokenStore(config.token_file)
    token = None
    token_state = "not present"
    try:
        token = store.load()
        if token is not None:
            token_state = "readable"
    except YandexDriveError:
        token_state = "invalid or unreadable"
    items = [
        (".env found", "yes" if Path(env_file).expanduser().exists() else "no"),
        ("Client ID configured", "yes" if config.client_id else "no"),
        ("Client Secret configured", "yes" if config.client_secret else "no"),
        ("Redirect URI", config.redirect_uri or "not configured"),
        ("OAuth scopes", ", ".join(config.scopes)),
        ("API base URL", config.api_base_url or "not configured"),
        ("Timeout", str(config.timeout)),
        ("Download chunk size", str(config.download_chunk_size)),
        ("Token-file path", str(config.token_file)),
        ("Token file exists", "yes" if store.exists() else "no"),
        ("Token file", token_state),
        ("Access token expired", "yes" if token and token.is_expired() else "no" if token else "unknown"),
        ("Refresh token exists", "yes" if token and token.refresh_token else "no"),
    ]
    width = max(len(label) for label, _ in items)
    for label, value in items:
        print(f"{label + ':':<{width + 1}} {value}")
    return 0


def _print_resource(resource: DiskResource) -> None:
    for label, value in (
        ("Path", resource.path),
        ("Name", resource.name),
        ("Type", resource.resource_type),
        ("Size", resource.size if resource.size is not None else "-"),
        ("MIME type", resource.mime_type or "-"),
        ("Created", resource.created.isoformat() if resource.created else "-"),
        ("Modified", resource.modified.isoformat() if resource.modified else "-"),
    ):
        print(f"{label + ':':<12}{value}")


def _run(args: argparse.Namespace, service_factory: Callable[[str], YandexDriveService]) -> int:
    if args.command == "diagnose":
        return _diagnose(args.env)
    service = service_factory(args.env)
    if args.command == "auth":
        service.authorize(force=args.force)
        print("Authorization completed.\nTokens saved.")
        return 0
    if args.command == "metadata":
        resource = service.get_metadata(args.remote_path)
        if args.json:
            print(json.dumps(resource.to_dict(), ensure_ascii=False))
        else:
            _print_resource(resource)
        return 0
    if args.command == "download":
        path = service.download_file_to(args.remote_path, args.output, overwrite=args.overwrite)
        payload = {"path": str(path), "bytes_written": path.stat().st_size}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"Download completed: {path}\nBytes written: {payload['bytes_written']}")
        return 0
    if args.command == "upload":
        resource = service.upload_file(args.local_path, args.remote_path, overwrite=args.overwrite)
        if args.json:
            print(json.dumps(resource.to_dict(), ensure_ascii=False))
        else:
            print(f"Upload completed: {resource.path}\nName: {resource.name}\nSize: {resource.size if resource.size is not None else '-'}")
        return 0
    raise YandexDriveError("Unknown command.")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process-compatible status code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose, args.debug)
    try:
        return _run(args, YandexDriveService.from_env)
    except (YandexDriveError, OSError) as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
