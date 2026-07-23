"""Общие проверки учётных данных для конфигурации и административной CLI."""

from __future__ import annotations

import re

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 64
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 1_024
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._@-]+$")
_COMMON_PASSWORDS = frozenset(
    {
        "admin",
        "admin/admin",
        "root",
        "root/root",
        "password",
        "password123",
        "password1234",
        "123456",
        "12345678",
        "qwerty",
        "letmein",
        "changeme",
        "changeme123",
        "admin123456",
        "adminpassword",
        "defaultpassword",
        "welcome123",
    }
)


def validate_username(value: str) -> str:
    """Принимает только стабильный, безопасный идентификатор без преобразований."""

    if not USERNAME_MIN_LENGTH <= len(value) <= USERNAME_MAX_LENGTH:
        raise ValueError(f"username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters")
    if value != value.strip():
        raise ValueError("username must not have leading or trailing whitespace")
    if any(ord(character) < 32 or ord(character) == 127 for character in value) or not _USERNAME_RE.fullmatch(value):
        raise ValueError("username contains unsupported characters")
    return value


def validate_password(value: str) -> str:
    """Проверяет пароль, не нормализуя и не возвращая его в сообщениях об ошибке."""

    if not PASSWORD_MIN_LENGTH <= len(value) <= PASSWORD_MAX_LENGTH:
        raise ValueError(f"password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters")
    if not value or value.isspace():
        raise ValueError("password must not be empty or whitespace only")
    if value.casefold() in _COMMON_PASSWORDS:
        raise ValueError("password must not use a common default value")
    return value
