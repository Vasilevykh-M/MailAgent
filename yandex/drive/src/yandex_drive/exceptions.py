"""Typed, safe errors raised by :mod:`yandex_drive`."""


class YandexDriveError(Exception):
    """Base class for expected Drive SDK errors."""


class ConfigurationError(YandexDriveError):
    """Local SDK configuration is missing or invalid."""


class OAuthError(YandexDriveError):
    """The OAuth authorization or token endpoint rejected a request."""


class AuthorizationCodeError(OAuthError):
    """An authorization code could not be exchanged safely."""


class TokenRefreshError(OAuthError):
    """A refresh token could not produce a usable access token."""


class TokenStorageError(YandexDriveError):
    """The local OAuth token file could not be used safely."""


class DriveApiError(YandexDriveError):
    """The Yandex Disk REST API or a temporary transfer URL failed."""


class AuthenticationError(DriveApiError):
    """The main API rejected credentials after one refresh retry."""


class ResourceNotFoundError(DriveApiError):
    """The requested Yandex Disk resource does not exist."""


class PermissionDeniedError(DriveApiError):
    """Yandex Disk denied access to the requested resource."""


class ResourceAlreadyExistsError(DriveApiError):
    """The remote resource exists and overwrite was not allowed."""


class InvalidResponseError(DriveApiError):
    """A server response did not have the documented safe shape."""


class UploadError(DriveApiError):
    """A direct upload to a temporary Yandex URL failed."""


class DownloadError(DriveApiError):
    """A direct download from a temporary Yandex URL failed."""


class InvalidRemotePathError(YandexDriveError):
    """A supplied remote path is absent or not a string."""


class LocalFileError(YandexDriveError):
    """A local source or destination file cannot be used safely."""
