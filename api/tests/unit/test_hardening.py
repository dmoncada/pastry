"""Unit regression tests for hardening defects at the model/config/security layer.

Each test here pins a specific defect: a char- vs byte-based content limit, a signed but
subject-less JWT, and production auth running on the development signing key. The
API-surface regressions (oversized bodies, the OpenAPI security document) live in
integration/test_hardening_api.py.
"""

from __future__ import annotations

import jwt
import pytest
from pastry_api.config import Settings
from pastry_api.security import InvalidToken, decode_access_token
from pastry_shared.models import MAX_CONTENT_BYTES, PasteCreate
from pydantic import ValidationError

pytestmark = pytest.mark.unit

# --- Content size limit --------------------------------------------------------------


def test_limit_counts_utf8_bytes_not_characters() -> None:
    """A char-based limit would let a multi-byte body through and blow the item cap."""
    # Each '€' is 3 UTF-8 bytes, so this is well under the limit in *characters*.
    content = "€" * (MAX_CONTENT_BYTES // 3 + 1)
    assert len(content) < MAX_CONTENT_BYTES
    with pytest.raises(ValidationError):
        PasteCreate(content=content)


# --- Malformed access tokens ---------------------------------------------------------


def test_signed_token_without_subject_is_invalid() -> None:
    """Previously raised KeyError('sub') and surfaced as a 500 rather than a 401."""
    settings = Settings(jwt_signing_key="k")
    token = jwt.encode(
        {"type": "access", "exp": 9_999_999_999},
        settings.jwt_signing_key,
        algorithm="HS256",
    )
    with pytest.raises(InvalidToken):
        decode_access_token(token, settings)


def test_token_with_empty_subject_is_invalid() -> None:
    settings = Settings(jwt_signing_key="k")
    token = jwt.encode(
        {"sub": "", "type": "access", "exp": 9_999_999_999},
        settings.jwt_signing_key,
        algorithm="HS256",
    )
    with pytest.raises(InvalidToken):
        decode_access_token(token, settings)


# --- Fail-open configuration ---------------------------------------------------------


def test_github_mode_rejects_the_dev_signing_key() -> None:
    """A deploy that forgets PASTRY_JWT_SIGNING_KEY must crash, not sign with a public key."""
    with pytest.raises(ValidationError, match="development default"):
        Settings(auth_mode="github")


def test_github_mode_accepts_a_real_signing_key() -> None:
    assert (
        Settings(auth_mode="github", jwt_signing_key="prod-key").auth_mode == "github"
    )


def test_dev_mode_still_needs_no_configuration() -> None:
    """Local work and the test suite must keep running with zero env setup."""
    assert Settings().auth_mode == "dev"


def test_unknown_auth_mode_is_rejected() -> None:
    """A typo'd mode must not quietly fall through to the non-dev branch.

    ``ty`` rejects this call statically, which is half the value of the Literal; the
    ignore is here because the mode usually arrives from the environment at runtime,
    where only validation can catch it.
    """
    with pytest.raises(ValidationError):
        Settings(auth_mode="githb", jwt_signing_key="prod-key")  # ty: ignore[invalid-argument-type]
