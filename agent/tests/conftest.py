from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mail_agent.config import RetrySettings
from mail_agent.models import MessageReference
from mail_agent.storage.processing_repository import ProcessingRepository


class FakeMail:
    def __init__(self, batches: list[list[MessageReference]]) -> None:
        self.batches = batches
        self.calls = 0
        self.read: list[tuple[str, str]] = []

    def list_unread_all(self, mailbox: str, batch_size: int, *, unread_only: bool = True) -> list[MessageReference]:
        del mailbox, batch_size, unread_only
        value = self.batches[min(self.calls, len(self.batches) - 1)]
        self.calls += 1
        return value

    def fetch_message(self, uid: str, mailbox: str) -> dict[str, object]:
        return {"uid": uid, "mailbox": mailbox, "message_id": f"<{uid}@example>", "attachments": []}

    def mark_read(self, uid: str, mailbox: str) -> None:
        self.read.append((uid, mailbox))


class FakeGraph:
    def __init__(self, status: str = "completed", fail_uid: str | None = None) -> None:
        self.status, self.fail_uid, self.seen = status, fail_uid, []

    def run(self, reference: MessageReference, temporary_dir: Path) -> dict[str, str]:
        self.seen.append(reference.uid)
        if reference.uid == self.fail_uid:
            raise RuntimeError("expected failure")
        return {"status": self.status}


@pytest.fixture
def repository(tmp_path: Path) -> ProcessingRepository:
    return ProcessingRepository(tmp_path / "state.sqlite3", RetrySettings())


@pytest.fixture
def references() -> list[MessageReference]:
    return [
        MessageReference(uid="2", mailbox="INBOX", message_id="<2>", date=datetime(2024, 1, 2, tzinfo=UTC)),
        MessageReference(uid="1", mailbox="INBOX", message_id="<1>", date=datetime(2024, 1, 1, tzinfo=UTC)),
    ]
