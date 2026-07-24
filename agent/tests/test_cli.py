from __future__ import annotations

from types import SimpleNamespace

from mail_agent import cli
from mail_agent.cli import _safe_check


def test_safe_check_returns_false_for_unavailable_service() -> None:
    def unavailable() -> bool:
        raise ConnectionRefusedError("expected")

    assert not _safe_check(unavailable)


def test_safe_check_returns_callback_result() -> None:
    assert _safe_check(lambda: True)
    assert not _safe_check(lambda: False)


def test_once_recovers_abandoned_node_executions_after_worker_lock(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    class Repository:
        def recover_abandoned_node_executions(self) -> int:
            calls.append("recover")
            return 1

    class Worker:
        repository = Repository()

        def once(self) -> int:
            calls.append("once")
            return 0

    class Runtime:
        worker = Worker()

        def close(self) -> None:
            calls.append("close")

    settings = SimpleNamespace(db_path=tmp_path / "state.sqlite3", log_level="ERROR")
    monkeypatch.setattr(cli, "load_settings", lambda _: settings)
    monkeypatch.setattr(cli, "build_runtime", lambda _: Runtime())

    assert cli.main(["once"]) == 0
    assert calls == ["recover", "once", "close"]
