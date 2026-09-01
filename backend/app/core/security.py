"""Password hashing and token issuance.

Passwords use stdlib hashlib.scrypt - a memory-hard KDF that needs no compiled
third-party wheel. Stored format is a self-describing string so parameters can
be raised later without invalidating existing hashes:

    scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings

# scrypt cost parameters. n=2**15 costs ~32MB per hash - deliberate.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_DK_LEN = 32
_SALT_BYTES = 16


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DK_LEN,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification. Never raises on malformed input."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=_b64d(salt_b64),
            n=int(n), r=int(r), p=int(p), dklen=len(_b64d(hash_b64)),
            maxmem=64 * 1024 * 1024,
        )
        return hmac.compare_digest(dk, _b64d(hash_b64))
    except (ValueError, TypeError, AttributeError):
        return False


def generate_password(length: int = 16) -> str:
    """Cryptographically random password with guaranteed character variety.

    Ambiguous glyphs (O/0, l/1/I) are excluded so credentials can be read off
    a screen and typed without error during an operational handover.
    """
    lower = "abcdefghijkmnopqrstuvwxyz"
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    symbols = "!@#$%^&*-_=+"
    pools = [lower, upper, digits, symbols]
    chars = [secrets.choice(pool) for pool in pools]
    everything = "".join(pools)
    chars += [secrets.choice(everything) for _ in range(length - len(pools))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def password_strength_errors(password: str) -> list[str]:
    """Policy check used when a user sets their own password."""
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters.")
    if not any(c.islower() for c in password):
        errors.append("Password must include a lowercase letter.")
    if not any(c.isupper() for c in password):
        errors.append("Password must include an uppercase letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Password must include a digit.")
    if not any(c in string.punctuation for c in password):
        errors.append("Password must include a symbol.")
    return errors


# ---- Tokens ---------------------------------------------------------------

ALGORITHM = "HS256"


def _encode(payload: dict[str, Any], expires: timedelta, token_type: str) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires
    body = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "typ": token_type,
        "jti": secrets.token_urlsafe(16),
        "iss": settings.APP_NAME,
    }
    return jwt.encode(body, settings.SECRET_KEY, algorithm=ALGORITHM), expires_at


def create_access_token(user_id: int, service_id: str, role: str) -> tuple[str, datetime]:
    return _encode(
        {"sub": str(user_id), "service_id": service_id, "role": role},
        timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
        "access",
    )


def create_refresh_token(user_id: int, remember: bool = False) -> tuple[str, datetime, str]:
    lifetime = (
        timedelta(days=settings.REMEMBER_ME_DAYS)
        if remember
        else timedelta(hours=settings.REFRESH_TOKEN_HOURS)
    )
    token, expires_at = _encode({"sub": str(user_id)}, lifetime, "refresh")
    return token, expires_at, decode_token(token)["jti"]


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify. Raises jwt.PyJWTError on any problem."""
    return jwt.decode(
        token, settings.SECRET_KEY, algorithms=[ALGORITHM], issuer=settings.APP_NAME
    )
