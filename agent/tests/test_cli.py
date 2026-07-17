from __future__ import annotations

from mail_agent.cli import _safe_check


def test_safe_check_returns_false_for_unavailable_service() -> None:
    def unavailable() -> bool:
        raise ConnectionRefusedError("expected")

    assert not _safe_check(unavailable)


def test_safe_check_returns_callback_result() -> None:
    assert _safe_check(lambda: True)
    assert not _safe_check(lambda: False)
