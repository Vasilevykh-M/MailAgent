from __future__ import annotations

from datetime import UTC, datetime

from mail_agent.integrations.mail import YandexMailAdapter


class Item:
    def __init__(self, uid: int) -> None:
        self.uid, self.message_id, self.date, self.size_bytes, self.flags = (
            str(uid),
            f"<{uid}>",
            datetime(2024, 1, uid, tzinfo=UTC),
            uid,
            {"\\Seen"},
        )


class Page:
    def __init__(self, items, more, offset) -> None:
        self.items, self.has_more, self.next_offset = items, more, offset


class Service:
    def __init__(self) -> None:
        self.offsets = []

    def list_messages(self, **kwargs):
        self.offsets.append(kwargs["offset"])
        return Page([Item(1), Item(2)] if kwargs["offset"] == 0 else [Item(3)], kwargs["offset"] == 0, 2)


def test_adapter_reads_all_pages_not_just_batch() -> None:
    adapter = object.__new__(YandexMailAdapter)
    adapter._service = Service()
    items = adapter.list_unread_all("INBOX", 2)
    assert [item.uid for item in items] == ["1", "2", "3"]
    assert adapter._service.offsets == [0, 2]
