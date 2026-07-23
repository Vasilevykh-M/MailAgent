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


def test_authentication_migration_creates_and_removes_only_auth_objects() -> None:
    migration_path = Path(__file__).parents[1] / "migrations/versions/0002_authentication.py"
    spec = importlib.util.spec_from_file_location("authentication_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    operations = RecordingOperations()
    migration.op = operations
    migration.upgrade()
    upgrade = "\n".join(operations.statements)
    assert "CREATE TABLE auth_users" in upgrade
    assert "CREATE TABLE auth_sessions" in upgrade
    assert "REFERENCES auth_users(id) ON DELETE CASCADE" in upgrade
    assert "CREATE UNIQUE INDEX auth_sessions_token_hash_key" in upgrade
    assert "auth_sessions_expires_at_idx" in upgrade

    operations.statements.clear()
    migration.downgrade()
    downgrade = "\n".join(operations.statements)
    assert "DROP TABLE IF EXISTS auth_sessions" in downgrade
    assert "DROP TABLE IF EXISTS auth_users" in downgrade
    assert "emails" not in downgrade
