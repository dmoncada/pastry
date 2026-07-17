"""Identifier helpers.

Two distinct identifiers, per ``spec.md``:

- **KSUID** — time-sortable, used *internally* as the DynamoDB sort key so an owner's
  pastes list in creation order. Never exposed to users.
- **slug** — a random, unguessable, Crockford-base32 string used as the *public*
  identifier in share links (``/p/<slug>``) and every CLI command. Its entropy is the
  security boundary for unlisted pastes, so it must come from a CSPRNG only.
"""

from __future__ import annotations

import secrets
import time

# Crockford base32: excludes I, L, O, U to avoid ambiguity; case-insensitive on decode.
_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# 25 chars * 5 bits = 125 bits of entropy — comfortably above the spec's >=120-bit floor.
_SLUG_LENGTH = 25


def new_slug(length: int = _SLUG_LENGTH) -> str:
    """Return a fresh, unguessable public slug (CSPRNG, Crockford base32)."""
    return "".join(secrets.choice(_CROCKFORD_ALPHABET) for _ in range(length))


def new_ksuid(*, when: float | None = None) -> str:
    """Return a fresh time-sortable internal id.

    TODO: replace this placeholder with a real KSUID implementation (e.g. ``svix-ksuid``)
    so lexical order matches creation order exactly. The current form is sortable-by-prefix
    but is not the canonical KSUID encoding.
    """
    timestamp = int(when if when is not None else time.time())
    random_suffix = secrets.token_hex(8)
    return f"{timestamp:010d}{random_suffix}"
