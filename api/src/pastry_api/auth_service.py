"""Token lifecycle: issue, rotate (single-use), and revoke — see Auth lifecycle in spec.

Rotation deletes the presented refresh row and issues a fresh one, so a replayed or
rotated-away token is rejected. Logout simply deletes the row."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pastry_shared.models import TokenPair

from pastry_api import auth_repo
from pastry_api.config import Settings
from pastry_api.security import (
    InvalidToken,
    create_access_token,
    generate_refresh_token,
    hash_token,
    parse_refresh_token,
)


def _now() -> datetime:
    return datetime.now(UTC)


def issue_tokens(github_id: str, settings: Settings) -> TokenPair:
    """Mint an access JWT + a fresh (stored) refresh token for ``github_id``."""
    access = create_access_token(github_id, settings)
    refresh = generate_refresh_token(github_id)
    expires_at = _now() + timedelta(seconds=settings.refresh_token_ttl)
    auth_repo.store_refresh(github_id, refresh.jti, refresh.token_hash, expires_at)
    return TokenPair(
        access_token=access,
        refresh_token=refresh.raw,
        expires_in=settings.access_token_ttl,
    )


def rotate_refresh(raw: str, settings: Settings) -> TokenPair:
    """Validate a refresh token, invalidate it, and issue a new pair.

    Raises :class:`~pastry_api.security.InvalidToken` if unknown, mismatched, or expired.
    """
    github_id, jti = parse_refresh_token(raw)
    item = auth_repo.get_refresh(github_id, jti)
    if item is None or item["token_hash"] != hash_token(raw):
        raise InvalidToken("unknown refresh token")
    if datetime.fromisoformat(item["expires_at"]) <= _now():
        auth_repo.delete_refresh(github_id, jti)
        raise InvalidToken("refresh token expired")
    auth_repo.delete_refresh(github_id, jti)  # single-use
    return issue_tokens(github_id, settings)


def revoke_refresh(raw: str) -> None:
    """Delete a refresh token's row (logout). No-op if the token is malformed/unknown."""
    try:
        github_id, jti = parse_refresh_token(raw)
    except InvalidToken:
        return
    auth_repo.delete_refresh(github_id, jti)
