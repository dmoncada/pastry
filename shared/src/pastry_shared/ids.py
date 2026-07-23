"""Identifier helpers.

Two distinct identifiers, per ``spec.md``:

- **KSUID** — time-sortable, used *internally* as the DynamoDB sort key so an owner's
  pastes list in creation order. Never exposed to users.
- **slug** — a random, unguessable, Crockford-base32 string used as the *public*
  identifier in share links (``/<slug>``) and every CLI command. Its entropy is the
  security boundary for unlisted pastes, so it must come from a CSPRNG only.
"""

from __future__ import annotations

import secrets

import base32_crockford
from ksuid import Ksuid

# 20 chars x 5 bits = 100 bits of entropy.
_SLUG_BITS = 100
_SLUG_LENGTH = 20


def new_slug() -> str:
    """Return a fresh, unguessable public slug."""
    value = secrets.randbits(_SLUG_BITS)

    # Encode as Crockford Base32 and left-pad with zeros to a fixed width.
    return base32_crockford.encode(value).zfill(_SLUG_LENGTH)


def new_ksuid() -> str:
    """Return a fresh, canonical KSUID."""
    return str(Ksuid())
