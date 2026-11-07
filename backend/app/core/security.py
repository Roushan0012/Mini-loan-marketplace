from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings

# Initialize password hasher using recommended Argon2 configuration
password_hasher = PasswordHash((Argon2Hasher(),))


class TokenSecurityError(ValueError):
    """Raised when a JWT access token is expired, malformed, or tampered with."""

    pass


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2 with a cryptographically secure salt."""
    if not password:
        raise ValueError("Password cannot be empty.")
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return password_hasher.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None,
    secret_key: Optional[str] = None,
    algorithm: Optional[str] = None,
) -> str:
    """Generate a signed JWT access token containing user ID subject and expiration.

    Contains no passwords or sensitive PII.
    """
    key = secret_key or settings.JWT_SECRET_KEY
    algo = algorithm or settings.JWT_ALGORITHM

    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, key, algorithm=algo)


def decode_access_token(
    token: str,
    secret_key: Optional[str] = None,
    algorithm: Optional[str] = None,
) -> Dict[str, Any]:
    """Decode and validate a JWT access token, enforcing expiration and signature."""
    key = secret_key or settings.JWT_SECRET_KEY
    allowed_algorithms = [algorithm or settings.JWT_ALGORITHM]

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=allowed_algorithms,
        )
        return payload
    except ExpiredSignatureError as exc:
        raise TokenSecurityError("Token signature has expired.") from exc
    except InvalidTokenError as exc:
        raise TokenSecurityError(f"Invalid token signature or payload: {exc}") from exc
