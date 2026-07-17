"""Repository-level tests for behavior the dev-mode (single-user) API can't exercise:
expiry filtering and cross-owner access control."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pastry_api import repository
from pastry_api.db import get_table, paste_sk, slug_gsi1pk, user_pk


def _put_expired(owner: str, slug: str) -> None:
    """Insert a paste whose expires_at is already in the past (TTL not yet swept)."""
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    get_table().put_item(
        Item={
            "PK": user_pk(owner),
            "SK": paste_sk("0000000000expired"),
            "GSI1PK": slug_gsi1pk(slug),
            "slug": slug,
            "content": "gone",
            "owner_github_id": owner,
            "created_at": past.isoformat(),
            "updated_at": past.isoformat(),
            "size": 4,
            "expires_at": past.isoformat(),
            "ttl": int(past.timestamp()),
        }
    )


def test_expired_paste_reads_as_not_found(table: None) -> None:
    _put_expired("alice", "EXPIREDSLUGEXPIREDSLUGEXP")
    with pytest.raises(repository.PasteNotFound):
        repository.get_paste("EXPIREDSLUGEXPIREDSLUGEXP")


def test_expired_paste_excluded_from_list(table: None) -> None:
    live = repository.create_paste("alice", "still here")
    _put_expired("alice", "EXPIREDSLUGEXPIREDSLUGEXP")
    slugs = [p.slug for p in repository.list_pastes("alice")]
    assert slugs == [live.slug]


def test_edit_by_non_owner_is_forbidden(table: None) -> None:
    paste = repository.create_paste("alice", "hers")
    with pytest.raises(repository.PasteForbidden):
        repository.update_paste("mallory", paste.slug, "hacked")


def test_delete_by_non_owner_is_forbidden(table: None) -> None:
    paste = repository.create_paste("alice", "hers")
    with pytest.raises(repository.PasteForbidden):
        repository.delete_paste("mallory", paste.slug)


def test_list_is_scoped_to_owner(table: None) -> None:
    repository.create_paste("alice", "a")
    repository.create_paste("bob", "b")
    assert len(repository.list_pastes("alice")) == 1
    assert len(repository.list_pastes("bob")) == 1


def _put_at_ksuid(owner: str, slug: str, ksuid: str) -> None:
    now = datetime.now(timezone.utc)
    get_table().put_item(
        Item={
            "PK": user_pk(owner),
            "SK": paste_sk(ksuid),
            "GSI1PK": slug_gsi1pk(slug),
            "slug": slug,
            "content": slug,
            "owner_github_id": owner,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "size": len(slug),
        }
    )


def test_list_orders_newest_ksuid_first(table: None) -> None:
    # Control the KSUIDs directly to assert the descending-SK ordering contract.
    _put_at_ksuid("alice", "OLDER", "0000000001aaaa")
    _put_at_ksuid("alice", "NEWER", "0000000002aaaa")
    assert [p.slug for p in repository.list_pastes("alice")] == ["NEWER", "OLDER"]
