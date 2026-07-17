"""Shared models and helpers used by both the Pastry backend and CLI."""

from __future__ import annotations

from pastry_shared.ids import new_ksuid, new_slug
from pastry_shared.models import (
    DeviceAuthResponse,
    Paste,
    PasteCreate,
    PasteUpdate,
    TokenPair,
    User,
)

__all__ = [
    "DeviceAuthResponse",
    "Paste",
    "PasteCreate",
    "PasteUpdate",
    "TokenPair",
    "User",
    "new_ksuid",
    "new_slug",
]
