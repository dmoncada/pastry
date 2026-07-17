"""Pydantic models shared across the API boundary (backend responses, CLI parsing).

These are the *domain/wire* models. DynamoDB item shapes (PK/SK/GSI keys) live in the
backend's persistence layer and are mapped to/from these — see ``spec.md`` for the
single-table sketch.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

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

    content: str
    expires_in: str | None = Field(
        default=None,
        description="Optional TTL shorthand: '1h', '1d', '1w'. None means never expires.",
    )


class PasteUpdate(BaseModel):
    """Request body / CLI input for editing a paste's content."""

    content: str


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
