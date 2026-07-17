"""Token primitives: signed access JWTs and opaque, hashed refresh tokens.

Access tokens are stateless HS256 JWTs the API verifies without a DB hit. Refresh tokens
are opaque strings whose SHA-256 hash is stored server-side; the raw value never touches
the database. A refresh token embeds ``github_id`` and ``jti`` so the API can locate its
row (``USER#<github_id> / REFRESH#<jti>``) without a secondary index."""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

import jwt

from pastry_api.config import Settings


class InvalidToken(Exception):
    """Raised when an access or refresh token is malformed, mismatched, or expired."""


def create_access_token(
    github_id: str, settings: Settings, now: int | None = None
) -> str:
    """Return a signed, short-lived access JWT carrying ``github_id`` as ``sub``."""
    issued = now if now is not None else int(time.time())
    payload = {
        "sub": github_id,
        "type": "access",
        "iat": issued,
        "exp": issued + settings.access_token_ttl,
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> str:
    """Verify an access JWT and return its ``github_id``. Raises :class:`InvalidToken`."""
    try:
        payload = jwt.decode(token, settings.jwt_signing_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    if payload.get("type") != "access":
        raise InvalidToken("not an access token")
    return str(payload["sub"])


def hash_token(raw: str) -> str:
    """Hash a raw refresh token for at-rest storage/comparison."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NewRefreshToken:
    raw: str  # given to the client; never stored
    jti: str  # storage key suffix
    token_hash: str  # stored server-side


def generate_refresh_token(github_id: str) -> NewRefreshToken:
    """Mint a new opaque refresh token as ``<github_id>.<jti>.<secret>``."""
    jti = secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    raw = f"{github_id}.{jti}.{secret}"
    return NewRefreshToken(raw=raw, jti=jti, token_hash=hash_token(raw))


def parse_refresh_token(raw: str) -> tuple[str, str]:
    """Split a refresh token into ``(github_id, jti)``. Raises :class:`InvalidToken`."""
    parts = raw.split(".", 2)
    if len(parts) != 3 or not all(parts):
        raise InvalidToken("malformed refresh token")
    return parts[0], parts[1]
