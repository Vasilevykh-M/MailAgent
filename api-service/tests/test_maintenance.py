from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest

from app.maintenance import ensure_partitions


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, statement: Any, *parameters: Any) -> None:
        self.statements.append((str(statement), parameters))


class RecordingTransaction(AbstractAsyncContextManager[RecordingConnection]):
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> RecordingConnection:
        return self.connection

    async def __aexit__(self, *args: object) -> None:
        return None


class RecordingEngine:
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    def begin(self) -> RecordingTransaction:
        return RecordingTransaction(self.connection)


class RecordingDatabase:
    def __init__(self) -> None:
        self.connection = RecordingConnection()
        self.engine = RecordingEngine(self.connection)


@pytest.mark.asyncio
async def test_partition_ddl_uses_utc_literals_without_query_parameters() -> None:
    database = RecordingDatabase()

    await ensure_partitions(database, months_ahead=0)  # type: ignore[arg-type]

    statements = database.connection.statements
    assert len(statements) == 6
    partition_statements = [statement for statement, _parameters in statements if "FOR VALUES FROM" in statement]
    assert len(partition_statements) == 4
    assert all(not parameters for _statement, parameters in statements)
    assert all(":start" not in statement and ":end" not in statement for statement in partition_statements)
    assert all("+00') TO ('" in statement for statement in partition_statements)
