"""Pydantic models shared across the API boundary (backend responses, CLI parsing).

These are the *domain/wire* models. DynamoDB item shapes (PK/SK/GSI keys) live in the
backend's persistence layer and are mapped to/from these — see ``spec.md`` for the
single-table sketch.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

# DynamoDB caps a single item at 400KB, and a paste's content shares that budget with its
# keys and metadata. 256KiB keeps a comfortable margin while staying far above any
# plausible paste, and turns an oversized body into a 422 instead of a write-time 500.
MAX_CONTENT_BYTES = 256 * 1024


def _within_size_limit(value: str) -> str:
    # Measured in UTF-8 bytes, not characters: that is what DynamoDB counts, so a
    # character-based limit would still let a multi-byte body blow the item cap.
    size = len(value.encode("utf-8"))
    if size > MAX_CONTENT_BYTES:
        raise ValueError(f"content is {size} bytes; the maximum is {MAX_CONTENT_BYTES}")
    return value


# Applied to inbound content only. Stored pastes are returned unvalidated, so an item
# written before this limit existed still reads back rather than 500-ing.
PasteContent = Annotated[str, AfterValidator(_within_size_limit)]

# --- User ---------------------------------------------------------------------------


class User(BaseModel):
    """A GitHub-authenticated account."""

    github_id: str
    login: str
    name: str | None = None
    created_at: datetime


# --- Paste --------------------------------------------------------------------------


class PasteCreate(BaseModel):
    """Request body / CLI input for creating a paste."""

    content: PasteContent
    expires_in: str | None = Field(
        default=None,
        description="Optional TTL shorthand: '1h', '1d', '1w'. None means never expires.",
    )


class PasteUpdate(BaseModel):
    """Request body / CLI input for editing a paste's content."""

    content: PasteContent


class Paste(BaseModel):
    """A stored paste as returned to clients. ``slug`` is the public id; KSUID is hidden."""

    slug: str
    content: str
    owner_github_id: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    size: int


# --- Auth ---------------------------------------------------------------------------


class DeviceAuthResponse(BaseModel):
    """What the backend hands the CLI to start the device-authorization grant."""

    device_code: str
    user_code: str
    verification_uri: str
    interval: int = 5
    expires_in: int = 900


class TokenPair(BaseModel):
    """What the backend issues after identity is verified."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # access-token lifetime in seconds
