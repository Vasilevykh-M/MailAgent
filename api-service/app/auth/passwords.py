"""Argon2id для паролей; plaintext и хеши за пределы этого модуля не выходят."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

_HASHER = PasswordHasher(type=Type.ID)
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$RHFi/rtnP9DB1xLcAcNmvA$jxbIG/hFT3O3X3PgIfJacZ5EX5FWJ/Dj1NCqCvp5MCA"
)


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _HASHER.check_needs_rehash(password_hash)
    except (InvalidHashError, VerificationError):
        return True


def dummy_password_hash() -> str:
    """Фиксированный Argon2id dummy-хеш для выравнивания login timing."""

    return _DUMMY_PASSWORD_HASH
