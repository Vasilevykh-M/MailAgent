from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any


class RecordingOperations:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: Any) -> None:
        self.statements.append(str(statement))


def test_initial_migration_executes_one_postgresql_command_at_a_time() -> None:
    migration_path = Path(__file__).parents[1] / "migrations/versions/0001_results_schema.py"
    spec = importlib.util.spec_from_file_location("results_schema_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    operations = RecordingOperations()
    migration.op = operations
    migration.upgrade()

    assert len(operations.statements) == 10
    assert all(
        len(re.findall(r"\bCREATE\s+(?:TABLE|INDEX)\b", statement, flags=re.IGNORECASE)) == 1
        for statement in operations.statements[:-1]
    )
    assert operations.statements[-1].lstrip().upper().startswith("DO $$")
