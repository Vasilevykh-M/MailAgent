from yandex_mail.config import YandexMailConfig
from yandex_mail.imap_client import ImapClient, parse_fetch_records, xoauth2_string


class FakeImap:
    def __init__(self, *args, **kwargs):
        self.callback_value = None
        self.logged_out = False

    def authenticate(self, mechanism, callback):
        self.callback_value = callback(b"")
        return "OK", [b"ok"]

    def select(self, mailbox, readonly=False):
        return "OK", [b"1"]

    def logout(self):
        self.logged_out = True
        return "BYE", [b"bye"]


def test_xoauth2_payload_is_raw_and_authenticates() -> None:
    config = YandexMailConfig(client_id="id", client_secret="secret", email="user@yandex.ru")
    made = []
    def factory(*args, **kwargs):
        value = FakeImap(*args, **kwargs)
        made.append(value)
        return value
    with ImapClient(config, lambda refresh: "token", imap_factory=factory) as client:
        client.select_mailbox("INBOX")
    assert xoauth2_string("user@yandex.ru", "token") == b"user=user@yandex.ru\x01auth=Bearer token\x01\x01"
    assert made[0].callback_value == xoauth2_string("user@yandex.ru", "token")
    assert b"dXNlcj0" not in made[0].callback_value


def test_parse_flag_only_fetch_response() -> None:
    records = parse_fetch_records([b"1 (UID 10 FLAGS (\\Seen custom))"])
    assert records[0].uid == "10" and records[0].flags == {"\\Seen", "custom"}
