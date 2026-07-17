"""Reusable OAuth 2.0 and IMAP XOAUTH2 SDK for Yandex Mail."""

from .config import YandexMailConfig
from .exceptions import (
    AttachmentSaveError, AuthorizationCodeError, ConfigurationError, ImapAuthenticationError,
    ImapConnectionError, MailboxError, MessageFlagError, MessageNotFoundError, MessageParseError,
    OAuthError, TokenRefreshError, TokenStorageError, YandexMailError,
)
from .models import Attachment, MailMessage, MessagePage, MessageStatus, MessageSummary
from .service import YandexMailService

__all__ = [
    "Attachment", "AttachmentSaveError", "AuthorizationCodeError", "ConfigurationError",
    "ImapAuthenticationError", "ImapConnectionError", "MailboxError", "MailMessage",
    "MessageFlagError", "MessageNotFoundError", "MessagePage", "MessageParseError",
    "MessageStatus", "MessageSummary", "OAuthError", "TokenRefreshError", "TokenStorageError",
    "YandexMailConfig", "YandexMailError", "YandexMailService",
]
