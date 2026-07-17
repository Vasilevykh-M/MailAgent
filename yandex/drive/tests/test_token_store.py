from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import os

import pytest

from yandex_drive import OAuthToken, TokenStorageError
from yandex_drive.token_store import TokenStore


def token() -> OAuthToken:
    return OAuthToken("access-value", "refresh-value", datetime.now(UTC) + timedelta(hours=1))


def test_round_trip_expiry_permissions_and_no_temporary_files(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "nested" / "drive.json")
    store.save(token())
    loaded = store.load()
    assert loaded and loaded.access_token == "access-value" and loaded.refresh_token == "refresh-value"
    assert loaded.expires_at.tzinfo is not None
    assert not list((tmp_path / "nested").glob("*.tmp"))
    assert not loaded.is_expired()
    assert OAuthToken("a", None, datetime.now(UTC)).is_expired()
    if os.name != "nt":
        assert store.path.stat().st_mode & 0o077 == 0


def test_atomic_replace_cleanup_and_safe_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = TokenStore(tmp_path / "token.json")
    calls: list[tuple[object, object]] = []

    def fail_replace(source: object, destination: object) -> None:
        calls.append((source, destination))
        raise OSError("failure")

    monkeypatch.setattr("yandex_drive.token_store.os.replace", fail_replace)
    with pytest.raises(TokenStorageError) as error:
        store.save(token())
    assert calls and not list(tmp_path.glob("*.tmp"))
    assert "access-value" not in str(error.value) and "refresh-value" not in str(error.value)


def test_missing_corrupted_and_repr_safety(tmp_path: Path) -> None:
    path = tmp_path / "token.json"
    store = TokenStore(path)
    assert store.load() is None
    path.write_text("{no", encoding="utf-8")
    with pytest.raises(TokenStorageError):
        store.load()
    assert "access-value" not in repr(token()) and "refresh-value" not in repr(token())


def test_expiration_leeway_and_refresh_token_persistence() -> None:
    now = datetime.now(UTC)
    token_value = OAuthToken("a", "r", now + timedelta(seconds=30))
    assert token_value.is_expired(now=now)
    assert not token_value.is_expired(leeway_seconds=0, now=now)
    restored = OAuthToken.from_dict(token_value.to_dict())
    assert restored.refresh_token == "r"
