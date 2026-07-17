from datetime import UTC, datetime

from yandex_mail.config import YandexMailConfig
from yandex_mail.imap_client import FetchRecord
from yandex_mail.service import YandexMailService


HEADER = b"Subject: Documents\r\nFrom: Sender <sender@example.com>\r\nTo: user@yandex.ru\r\nDate: Sat, 11 Jul 2026 10:30:00 +0300\r\nMessage-ID: <x>\r\nContent-Type: text/plain\r\n\r\n"


class FakeClient:
    def __init__(self, *args):
        self.flags = {"\\Flagged"}
        self.stores = []
        self.criteria = []

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def select_mailbox(self, mailbox): self.mailbox = mailbox
    def search(self, criteria): self.criteria = criteria; return ["1", "2"]
    def fetch(self, uid_set, fields):
        ids = uid_set.split(",")
        return [FetchRecord(uid, int(uid), set(self.flags), 123, None, HEADER if "HEADER" in fields else None, "") for uid in ids]
    def store(self, uid_set, op, flags):
        self.stores.append((uid_set, op, flags))
        if op.startswith("+"): self.flags.update(flags)
        else: self.flags.difference_update(flags)


def test_list_uses_search_and_batched_header_fetch() -> None:
    clients = []
    def factory(*args):
        client = FakeClient(); clients.append(client); return client
    config = YandexMailConfig(client_id="id", client_secret="secret", email="u@yandex.ru")
    service = YandexMailService(config, imap_client_factory=factory)
    page = service.list_messages(status="unread", sender="sender@example.com", limit=1)
    assert page.total == 2 and len(page.items) == 1
    assert clients[0].criteria[:3] == ["UNSEEN", "FROM", '"sender@example.com"']


def test_bulk_flag_update_is_verified() -> None:
    clients = []
    def factory(*args):
        client = FakeClient(); clients.append(client); return client
    config = YandexMailConfig(client_id="id", client_secret="secret", email="u@yandex.ru")
    statuses = YandexMailService(config, imap_client_factory=factory).mark_many_as_read(["1", "2"])
    assert all(item.is_read for item in statuses)
    assert clients[0].stores == [("1,2", "+FLAGS.SILENT", {"\\Seen"})]
