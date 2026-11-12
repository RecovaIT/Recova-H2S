"""Password hashing, opaque session tokens, CSRF tokens and field encryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_hasher = PasswordHasher()

PASSWORD_MIN_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> list[str]:
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if not any(c.isdigit() for c in password):
        problems.append("Password must contain a digit")
    if not any(c.isalpha() for c in password):
        problems.append("Password must contain a letter")
    return problems


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Tokens are stored as keyed SHA-256 digests; raw tokens never hit the DB."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


@lru_cache
def _fernet() -> Fernet:
    s = get_settings()
    if s.field_encryption_key:
        key = s.field_encryption_key.encode()
    else:
        key = base64.urlsafe_b64encode(hashlib.sha256(("fernet:" + s.secret_key).encode()).digest())
    return Fernet(key)


def encrypt_str(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    return _fernet().encrypt(value.encode()).decode()


def decrypt_str(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def mask(value: str | None, keep: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)
