"""Интерактивная административная CLI пользователей и очистки сессий."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from ..config import get_settings
from ..db import Database
from .repository import AuthRepository
from .service import AuthenticationService, UserManagementError


def _password_from_tty() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise UserManagementError("Passwords do not match")
    return password


async def _service() -> tuple[AuthenticationService, Database]:
    settings = get_settings()
    database = Database(settings)
    return AuthenticationService(AuthRepository(database.sessions), settings), database


async def _users_run(args: argparse.Namespace) -> str:
    service, database = await _service()
    try:
        if args.command == "create":
            user = await service.create_user(args.username, _password_from_tty())
            return f"User {user.username} created"
        if args.command == "set-password":
            await service.set_password(args.username, _password_from_tty())
            return "Password updated; active sessions revoked"
        if args.command == "activate":
            await service.set_active(args.username, True)
            return "User activated"
        if args.command == "deactivate":
            await service.set_active(args.username, False)
            return "User deactivated; active sessions revoked"
        raise UserManagementError("Unknown users command")
    finally:
        await database.close()


async def _auth_run(args: argparse.Namespace) -> int:
    service, database = await _service()
    try:
        return await service.cleanup_sessions(revoked_retention_seconds=args.revoked_retention_seconds)
    finally:
        await database.close()


def users_main() -> None:
    parser = argparse.ArgumentParser(prog="mail-results-users")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "set-password", "activate", "deactivate"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--username", required=True)
    args = parser.parse_args()
    try:
        print(asyncio.run(_users_run(args)))
    except (UserManagementError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


def auth_main() -> None:
    parser = argparse.ArgumentParser(prog="mail-results-auth")
    commands = parser.add_subparsers(dest="command", required=True)
    cleanup = commands.add_parser("cleanup-sessions")
    cleanup.add_argument("--revoked-retention-seconds", type=int, default=None)
    args = parser.parse_args()
    if args.revoked_retention_seconds is not None and args.revoked_retention_seconds < 300:
        parser.error("--revoked-retention-seconds must be at least 300")
    try:
        print(asyncio.run(_auth_run(args)))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
