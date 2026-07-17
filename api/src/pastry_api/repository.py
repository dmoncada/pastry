"""Paste persistence over the single DynamoDB table.

Maps between the domain :class:`~pastry_shared.models.Paste` and the item shape sketched
in ``spec.md``. Reads resolve public slugs via GSI1; writes are keyed by the owner's
partition + the paste's KSUID. Expiry is enforced in code on read (DynamoDB TTL deletion
is only eventual), so an expired paste reads as "not found" even before it is swept.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.conditions import Key
from pastry_shared import new_ksuid, new_slug
from pastry_shared.models import Paste

from pastry_api.db import get_table, paste_sk, slug_gsi1pk, user_pk

Item = dict[str, Any]

_EXPIRY_DELTAS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}


class PasteNotFound(Exception):
    """Raised when a slug resolves to nothing (missing, deleted, or expired)."""


class PasteForbidden(Exception):
    """Raised when a caller tries to mutate a paste they do not own."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_expiry(expires_in: str | None, now: datetime) -> datetime | None:
    """Turn an expiry shorthand ('1h'/'1d'/'1w') into an absolute UTC instant."""
    if expires_in is None:
        return None
    try:
        return now + _EXPIRY_DELTAS[expires_in]
    except KeyError:
        raise ValueError(f"invalid expiry {expires_in!r}; expected one of 1h, 1d, 1w")


def _is_expired(item: Item, now: datetime) -> bool:
    raw = item.get("expires_at")
    return raw is not None and datetime.fromisoformat(raw) <= now


def _from_item(item: Item) -> Paste:
    expires_at = item.get("expires_at")
    return Paste(
        slug=item["slug"],
        content=item["content"],
        owner_github_id=item["owner_github_id"],
        created_at=datetime.fromisoformat(item["created_at"]),
        updated_at=datetime.fromisoformat(item["updated_at"]),
        expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
        size=int(item["size"]),
    )


def _get_item_by_slug(slug: str) -> Item | None:
    """Return the raw item behind a slug via GSI1, or None. Slugs are globally unique."""
    resp = get_table().query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(slug_gsi1pk(slug)),
        Limit=1,
    )
    items: list[Item] = resp.get("Items", [])
    return items[0] if items else None


def create_paste(
    owner_github_id: str, content: str, expires_in: str | None = None
) -> Paste:
    """Create a paste owned by ``owner_github_id`` and return it (with its public slug)."""
    now = _now()
    expires_at = _parse_expiry(expires_in, now)
    ksuid = new_ksuid()
    paste = Paste(
        slug=new_slug(),
        content=content,
        owner_github_id=owner_github_id,
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
        size=len(content.encode("utf-8")),
    )
    item: Item = {
        "PK": user_pk(owner_github_id),
        "SK": paste_sk(ksuid),
        "GSI1PK": slug_gsi1pk(paste.slug),
        "slug": paste.slug,
        "content": paste.content,
        "owner_github_id": owner_github_id,
        "created_at": paste.created_at.isoformat(),
        "updated_at": paste.updated_at.isoformat(),
        "size": paste.size,
    }
    if expires_at is not None:
        item["expires_at"] = expires_at.isoformat()
        item["ttl"] = int(expires_at.timestamp())
    get_table().put_item(Item=item)
    return paste


def list_pastes(owner_github_id: str) -> list[Paste]:
    """Return the owner's non-expired pastes, newest first (descending KSUID)."""
    now = _now()
    resp = get_table().query(
        KeyConditionExpression=Key("PK").eq(user_pk(owner_github_id))
        & Key("SK").begins_with("PASTE#"),
        ScanIndexForward=False,
    )
    return [_from_item(i) for i in resp.get("Items", []) if not _is_expired(i, now)]


def get_paste(slug: str) -> Paste:
    """Public read by slug. Raises :class:`PasteNotFound` if missing/expired."""
    item = _get_item_by_slug(slug)
    if item is None or _is_expired(item, _now()):
        raise PasteNotFound(slug)
    return _from_item(item)


def update_paste(owner_github_id: str, slug: str, content: str) -> Paste:
    """Replace a paste's content. Owner only; raises NotFound/Forbidden accordingly."""
    item = _get_item_by_slug(slug)
    if item is None or _is_expired(item, _now()):
        raise PasteNotFound(slug)
    if item["owner_github_id"] != owner_github_id:
        raise PasteForbidden(slug)
    item["content"] = content
    item["size"] = len(content.encode("utf-8"))
    item["updated_at"] = _now().isoformat()
    get_table().put_item(Item=item)
    return _from_item(item)


def delete_paste(owner_github_id: str, slug: str) -> None:
    """Delete a paste. Owner only; raises NotFound/Forbidden accordingly."""
    item = _get_item_by_slug(slug)
    if item is None or _is_expired(item, _now()):
        raise PasteNotFound(slug)
    if item["owner_github_id"] != owner_github_id:
        raise PasteForbidden(slug)
    get_table().delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
