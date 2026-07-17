"""Independent OAuth 2.0 Authorization Code Flow for Yandex Drive."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Callable, Mapping
from urllib.parse import urlencode
import webbrowser

import requests

from .config import YandexDriveConfig
from .exceptions import AuthorizationCodeError, OAuthError, TokenRefreshError
from .token_store import OAuthToken


LOGGER = logging.getLogger(__name__)
AUTHORIZE_ENDPOINT = "https://oauth.yandex.ru/authorize"
TOKEN_ENDPOINT = "https://oauth.yandex.ru/token"


class OAuthClient:
    """Build authorization URLs and exchange or refresh Drive OAuth tokens."""

    def __init__(
        self,
        config: YandexDriveConfig,
        session: requests.Session | None = None,
        *,
        authorization_code_input: Callable[[str], str] = input,
        authorization_url_output: Callable[[str], None] = print,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self._authorization_code_input = authorization_code_input
        self._authorization_url_output = authorization_url_output
        self._now_provider = now_provider

    def authorization_url(self) -> str:
        """Return a user-facing URL requesting the configured Drive scopes."""

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
        }
        return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"

    def authorize_interactively(
        self,
        *,
        input_func: Callable[[str], str] | None = None,
        output_func: Callable[[str], None] | None = None,
        open_browser: bool = True,
    ) -> OAuthToken:
        """Present the URL, collect a verification code, and exchange it."""

        output = output_func or self._authorization_url_output
        read_code = input_func or self._authorization_code_input
        url = self.authorization_url()
        output("Open this URL in a browser and authorize Yandex Disk:")
        output(url)
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                LOGGER.debug("Could not open the authorization URL in a browser.", exc_info=True)
        code = read_code("Paste the Yandex verification code: ").strip()
        if not code:
            raise AuthorizationCodeError("No authorization code was provided.")
        return self.exchange_code(code)

    def exchange_code(self, code: str) -> OAuthToken:
        """Exchange a user-entered authorization code without exposing it."""

        if not isinstance(code, str) or not code.strip():
            raise AuthorizationCodeError("No authorization code was provided.")
        return self._request_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            },
            AuthorizationCodeError,
        )

    def refresh(self, refresh_token: str) -> OAuthToken:
        """Refresh an access token, retaining the old refresh token if omitted."""

        if not isinstance(refresh_token, str) or not refresh_token:
            raise TokenRefreshError("No refresh token is available.")
        token = self._request_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            },
            TokenRefreshError,
        )
        if not token.refresh_token:
            token.refresh_token = refresh_token
        return token

    def _request_token(
        self, payload: dict[str, str], error_type: type[OAuthError]
    ) -> OAuthToken:
        try:
            response = self.session.post(TOKEN_ENDPOINT, data=payload, timeout=self.config.timeout)
        except requests.RequestException as exc:
            raise error_type("Could not contact the Yandex OAuth service.") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise error_type("Yandex OAuth returned an invalid response.") from exc
        if not bool(getattr(response, "ok", False)) or not isinstance(body, Mapping):
            raise error_type("Yandex OAuth rejected the authorization request.")
        try:
            return OAuthToken.from_oauth_response(body, now=self._now_provider() if self._now_provider else None)
        except Exception as exc:
            raise error_type("Yandex OAuth returned an invalid response.") from exc
