from pathlib import Path

from yandex_mail.models import Attachment, MessageStatus


def test_status_is_case_insensitive_and_preserves_custom_flags() -> None:
    status = MessageStatus("1", "INBOX", {"\\sEeN", "\\FLAGGED", "custom"})
    assert status.is_read and not status.is_unread and status.is_important
    assert status.custom_flags == {"custom"}
    assert status.to_dict()["flags"] == ["\\FLAGGED", "\\sEeN", "custom"]


def test_attachment_dict_and_safe_unique_save(tmp_path: Path) -> None:
    attachment = Attachment("../../report.txt", "text/plain", "attachment", None, "utf-8", 2, b"ok")
    assert attachment.to_dict(include_data=True)["data"] == "b2s="
    first = attachment.save(tmp_path / attachment.filename)
    second = attachment.save(tmp_path / attachment.filename)
    assert first.parent == tmp_path.resolve()
    assert first.name == "report.txt" and second.name == "report_2.txt"


def test_absolute_sender_filename_never_selects_an_absolute_destination(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    attachment = Attachment("/etc/passwd", "text/plain", "attachment", None, None, 2, b"ok")
    saved = attachment.save(Path("output") / attachment.filename)
    assert saved.parent == tmp_path
    assert saved.name == "passwd"
