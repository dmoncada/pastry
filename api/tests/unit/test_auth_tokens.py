"""Unit tests for the JWT access-token lifecycle — pure crypto, no I/O.

Refresh-token rotation/revocation (which touches the moto table) and the auth endpoints
live in integration/test_auth.py."""

from __future__ import annotations

import pytest
from pastry_api.config import Settings
from pastry_api.security import InvalidToken, create_access_token, decode_access_token

pytestmark = pytest.mark.unit


def test_access_token_roundtrip() -> None:
    settings = Settings(jwt_signing_key="k")
    token = create_access_token("42", settings)
    assert decode_access_token(token, settings) == "42"


def test_decode_rejects_wrong_key() -> None:
    token = create_access_token("42", Settings(jwt_signing_key="right"))
    with pytest.raises(InvalidToken):
        decode_access_token(token, Settings(jwt_signing_key="wrong"))
