from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from yandex_drive import AuthorizationCodeError, TokenRefreshError, YandexDriveConfig
from yandex_drive.oauth import OAuthClient

from .conftest import FakeResponse, FakeSession


def config() -> YandexDriveConfig:
    return YandexDriveConfig(client_id="client-id", client_secret="client-secret")


def test_url_exchange_refresh_rotation_and_secret_safety() -> None:
    session = FakeSession([
        FakeResponse(body={"access_token": "access", "refresh_token": "new-refresh", "expires_in": 90}),
        FakeResponse(body={"access_token": "fresh", "expires_in": 120}),
    ])
    now = datetime(2026, 1, 1, tzinfo=UTC)
    client = OAuthClient(config(), session, now_provider=lambda: now)
    url = client.authorization_url()
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["https://oauth.yandex.ru/verification_code"]
    assert set(query["scope"][0].split()) == {"cloud_api:disk.read", "cloud_api:disk.write"}
    assert "client-secret" not in url
    token = client.exchange_code("verification-code")
    assert token.expires_at == now + timedelta(seconds=90)
    refreshed = client.refresh("old-refresh")
    assert refreshed.refresh_token == "old-refresh"
    assert session.calls[0][1]["data"]["code"] == "verification-code"


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        (FakeResponse(status_code=400, body={"error": "bad"}), AuthorizationCodeError),
        (FakeResponse(body=None, json_error=True), AuthorizationCodeError),
        (FakeResponse(body={"refresh_token": "r"}), AuthorizationCodeError),
    ],
)
def test_code_errors_are_typed_and_safe(response: FakeResponse, exception: type[Exception]) -> None:
    client = OAuthClient(config(), FakeSession([response]))
    with pytest.raises(exception) as error:
        client.exchange_code("very-secret-code")
    assert "very-secret-code" not in str(error.value) and "client-secret" not in str(error.value)


def test_refresh_error_and_interactive_callbacks() -> None:
    client = OAuthClient(config(), FakeSession([FakeResponse(status_code=400, body={})]))
    with pytest.raises(TokenRefreshError):
        client.refresh("refresh")
    with pytest.raises(AuthorizationCodeError):
        OAuthClient(config(), FakeSession([]), authorization_code_input=lambda _: "").authorize_interactively(open_browser=False)
