"""Security utilities: password hashing and JWT tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from jose import JWTError, jwt

from app.config import settings


class TokenError(Exception):
    """Raised when a JWT cannot be decoded or is invalid."""


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True iff *plain* matches the bcrypt *hashed* value."""
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(*, user_id: str, company_id: str, role_code: str | None,
                  token_type: str, expires_delta: timedelta) -> str:
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "role_code": role_code,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(*, user_id: str, company_id: str, role_code: str | None) -> str:
    return _create_token(user_id=user_id, company_id=company_id, role_code=role_code,
                         token_type="access",
                         expires_delta=timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(*, user_id: str, company_id: str, role_code: str | None) -> str:
    return _create_token(user_id=user_id, company_id=company_id, role_code=role_code,
                         token_type="refresh",
                         expires_delta=timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
