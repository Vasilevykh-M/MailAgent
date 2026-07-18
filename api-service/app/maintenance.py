"""Утилиты обслуживания: подготовка партиций и уборка неподтверждённых S3-объектов."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from .config import get_settings
from .db import Database, EmailLocator
from .storage.s3 import S3Storage


def _month(value: datetime, delta: int) -> datetime:
    index = value.year * 12 + value.month - 1 + delta
    return value.replace(year=index // 12, month=index % 12 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _partition_bound(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00")


async def ensure_partitions(database: Database, months_ahead: int) -> None:
    """Безопасно создаёт именованные по внутренней дате monthly partitions и default fallback."""

    now = datetime.now(UTC)
    async with database.engine.begin() as connection:
        for base in ("emails", "email_attachments"):
            await connection.execute(text(f"CREATE TABLE IF NOT EXISTS {base}_default PARTITION OF {base} DEFAULT"))
        for offset in range(-1, months_ahead + 1):
            start = _month(now, offset)
            end = _month(start, 1)
            suffix = start.strftime("%Y_%m")
            # suffix строится только из datetime, не из запроса пользователя.
            for base in ("emails", "email_attachments"):
                await connection.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {base}_{suffix} PARTITION OF {base} "
                        f"FOR VALUES FROM ('{_partition_bound(start)}') TO ('{_partition_bound(end)}')"
                    )
                )


async def _run() -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        await ensure_partitions(database, settings.partitions_months_ahead)
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="mail-results-partitions")
    parser.parse_args()
    asyncio.run(_run())


async def _cleanup(older_than_hours: int) -> int:
    settings = get_settings()
    database, storage = Database(settings), S3Storage(settings)
    cutoff, deleted = datetime.now(UTC) - timedelta(hours=older_than_hours), 0
    try:
        for prefix in storage.orphan_prefixes(older_than=cutoff):
            record_id = prefix.rstrip("/").split("/")[-1]
            async with database.sessions() as session:
                locator = (
                    await session.execute(select(EmailLocator.record_id).where(EmailLocator.record_id == record_id))
                ).scalar_one_or_none()
            if locator is None:
                deleted += storage.delete_prefix(prefix)
    finally:
        await database.close()
    return deleted


def orphan_main() -> None:
    parser = argparse.ArgumentParser(prog="mail-results-orphans")
    parser.add_argument("--older-than-hours", type=int, default=72)
    args = parser.parse_args()
    if args.older_than_hours < 1:
        raise SystemExit("--older-than-hours must be at least 1")
    print(asyncio.run(_cleanup(args.older_than_hours)))
