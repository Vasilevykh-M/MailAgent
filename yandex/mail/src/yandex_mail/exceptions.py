"""Exception hierarchy for :mod:`yandex_mail`."""


class YandexMailError(Exception):
    """Base class for expected Yandex Mail SDK errors."""


class ConfigurationError(YandexMailError):
    """Invalid or incomplete local configuration."""


class OAuthError(YandexMailError):
    """OAuth endpoint or authorization flow failure."""


class AuthorizationCodeError(OAuthError):
    """Yandex rejected the submitted authorization code."""


class TokenStorageError(YandexMailError):
    """Local token storage could not be read or written safely."""


class TokenRefreshError(OAuthError):
    """A stored refresh token could not be exchanged."""


class ImapConnectionError(YandexMailError):
    """A connection to the IMAP server failed."""


class ImapAuthenticationError(ImapConnectionError):
    """IMAP XOAUTH2 authentication failed after one retry."""


class MailboxError(YandexMailError):
    """An IMAP mailbox could not be selected or closed."""


class MessageNotFoundError(YandexMailError):
    """The requested UID does not exist in the selected mailbox."""


class MessageFlagError(YandexMailError):
    """A flag operation was invalid or rejected by the server."""


class AttachmentSaveError(YandexMailError):
    """An attachment could not be saved inside the requested directory."""


class MessageParseError(YandexMailError):
    """A MIME message could not be parsed safely."""
