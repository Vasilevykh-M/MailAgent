from pathlib import Path

from yandex_mail.parser import parse_message


RAW = b"""From: =?utf-8?b?0KLQtdGB0YI=?= <sender@example.com>\r
To: User <user@example.com>\r
Subject: =?utf-8?b?0J/RgNC40LLQtdGC?=\r
Date: Sat, 11 Jul 2026 10:30:00 +0300\r
X-Duplicate: first\r
X-Duplicate: second\r
MIME-Version: 1.0\r
Content-Type: multipart/mixed; boundary=outer\r
\r
--outer\r
Content-Type: multipart/alternative; boundary=inner\r
\r
--inner\r
Content-Type: text/plain; charset=unknown-charset\r
\r
plain body\r
--inner\r
Content-Type: text/html; charset=utf-8\r
\r
<b>html body</b>\r
--inner--\r
--outer\r
Content-Type: application/octet-stream; name="../../file.txt"\r
Content-Disposition: attachment; filename="../../file.txt"\r
Content-Transfer-Encoding: base64\r
\r
aGVsbG8=\r
--outer--\r
"""


def test_parse_nested_mime_and_safe_attachment_save(tmp_path: Path) -> None:
    message = parse_message(RAW, uid="9", mailbox="INBOX", flags={"\\Seen"})
    assert message.subject == "Привет"
    assert message.text_plain == "plain body"
    assert message.text_html == "<b>html body</b>"
    assert len(message.attachments) == 1 and message.attachments[0].data == b"hello"
    assert len([h for h in message.headers if h[0] == "X-Duplicate"]) == 2
    assert message.save_attachments(tmp_path)[0].name == "file.txt"
    eml = message.save_eml(tmp_path / "message.eml")
    assert eml.read_bytes() == RAW


def test_html_only_and_empty_message_are_supported() -> None:
    html = b"Subject: x\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>x</p>"
    parsed = parse_message(html, uid="1", mailbox="INBOX")
    assert parsed.text_plain is None and parsed.text_html == "<p>x</p>"
