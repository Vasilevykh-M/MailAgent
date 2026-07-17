"""Yandex OAuth 2.0 Authorization Code Flow implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Callable
from urllib.parse import urlencode
import webbrowser

import requests

from .config import YandexMailConfig
from .exceptions import AuthorizationCodeError, OAuthError, TokenRefreshError
from .token_store import OAuthToken


LOGGER = logging.getLogger(__name__)
AUTHORIZE_ENDPOINT = "https://oauth.yandex.ru/authorize"
TOKEN_ENDPOINT = "https://oauth.yandex.ru/token"


class OAuthClient:
    """Exchange Yandex authorization codes and refresh tokens without logging them."""

    def __init__(self, config: YandexMailConfig, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    def authorization_url(self) -> str:
        """Build the URL the user opens to grant ``mail:imap_full`` access."""

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": self.config.oauth_scope,
        }
        return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"

    def authorize_interactively(
        self,
        *,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
        open_browser: bool = True,
    ) -> OAuthToken:
        """Open/print the URL and exchange the verification code entered by the user."""

        url = self.authorization_url()
        output_func("Open this URL in a browser and authorize Yandex Mail:")
        output_func(url)
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:  # Browser launch is a convenience only.
                LOGGER.debug("Could not open the authorization URL in a browser.", exc_info=True)
        code = input_func("Paste the Yandex verification code: ").strip()
        if not code:
            raise AuthorizationCodeError("No authorization code was provided.")
        return self.exchange_code(code)

    def exchange_code(self, code: str) -> OAuthToken:
        """Exchange an authorization code for access and refresh tokens."""

        if not code.strip():
            raise AuthorizationCodeError("No authorization code was provided.")
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        return self._request_token(payload, AuthorizationCodeError)

    def refresh(self, refresh_token: str) -> OAuthToken:
        """Refresh an access token, preserving the old refresh token if omitted."""

        if not refresh_token:
            raise TokenRefreshError("No refresh token is available.")
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        token = self._request_token(payload, TokenRefreshError)
        # Although Yandex normally returns a refresh token, preserving the old
        # value is safer and supports OAuth providers that rotate conditionally.
        if not token.refresh_token:
            token.refresh_token = refresh_token
        return token

    def _request_token(self, payload: dict[str, str], error_type: type[OAuthError]) -> OAuthToken:
        try:
            response = self.session.post(TOKEN_ENDPOINT, data=payload, timeout=self.config.timeout)
        except requests.RequestException as exc:
            raise error_type("Could not contact the Yandex OAuth service.") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise error_type("Yandex OAuth returned an invalid response.") from exc
        if not response.ok or not isinstance(body, dict) or not body.get("access_token"):
            # OAuth's text may contain user-specific details. It is not included
            # in the exception or logs, and neither are request credentials.
            raise error_type("Yandex OAuth rejected the authorization request.")
        refresh = body.get("refresh_token", "")
        if not isinstance(refresh, str):
            raise error_type("Yandex OAuth returned an invalid response.")
        try:
            seconds = int(body.get("expires_in", 3600))
        except (TypeError, ValueError):
            seconds = 3600
        return OAuthToken(
            access_token=str(body["access_token"]),
            refresh_token=refresh,
            expires_at=datetime.now(UTC) + timedelta(seconds=max(seconds, 0)),
            token_type=str(body.get("token_type") or "Bearer"),
        )
