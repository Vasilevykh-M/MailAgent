from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest

from yandex_mail.exceptions import TokenStorageError
from yandex_mail.token_store import OAuthToken, TokenStore


def test_token_store_atomic_round_trip_and_expiry(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    token = OAuthToken("access", "refresh", datetime.now(UTC) + timedelta(hours=1))
    store = TokenStore(path)
    store.save(token)
    assert store.load().access_token == "access"  # type: ignore[union-attr]
    assert not list(tmp_path.glob(".*.tmp"))
    assert not token.is_expired()
    assert OAuthToken("a", "r", datetime.now(UTC)).is_expired()


def test_corrupt_token_file_is_safe_error(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(TokenStorageError):
        TokenStore(path).load()
