from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from yandex_mail.config import YandexMailConfig
from yandex_mail.exceptions import AuthorizationCodeError, TokenRefreshError
from yandex_mail.oauth import OAuthClient


class Response:
    def __init__(self, body, ok=True):
        self._body, self.ok = body, ok

    def json(self):
        return self._body


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def _config() -> YandexMailConfig:
    return YandexMailConfig(client_id="id", client_secret="secret", email="u@yandex.ru")


def test_authorization_url_and_code_exchange() -> None:
    session = Session(Response({"access_token": "access", "refresh_token": "refresh", "expires_in": 100}))
    client = OAuthClient(_config(), session)
    query = parse_qs(urlparse(client.authorization_url()).query)
    assert query["redirect_uri"] == ["https://oauth.yandex.ru/verification_code"]
    assert query["scope"] == ["mail:imap_full"]
    token = client.exchange_code("code")
    assert token.access_token == "access" and token.refresh_token == "refresh"
    assert session.calls[0][1]["data"]["code"] == "code"


def test_oauth_errors_do_not_include_credentials() -> None:
    client = OAuthClient(_config(), Session(Response({"error": "bad"}, ok=False)))
    with pytest.raises(AuthorizationCodeError) as error:
        client.exchange_code("very-secret-code")
    assert "very-secret-code" not in str(error.value)
    with pytest.raises(TokenRefreshError):
        client.refresh("refresh")
