"""Persistence for users and refresh tokens on the single DynamoDB table.

PK                  SK             Notes
USER#<github_id>    PROFILE        login, name, created_at
USER#<github_id>    REFRESH#<jti>  token_hash, expires_at, ttl
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from pastry_shared.models import User

from pastry_api.db import get_table, user_pk

Item = dict[str, Any]

_PROFILE_SK = "PROFILE"


def _refresh_sk(jti: str) -> str:
    return f"REFRESH#{jti}"


def get_user(github_id: str) -> User | None:
    resp = get_table().get_item(Key={"PK": user_pk(github_id), "SK": _PROFILE_SK})
    item = cast("Item | None", resp.get("Item"))
    if item is None:
        return None
    return User(
        github_id=item["github_id"],
        login=item["login"],
        name=item.get("name"),
        created_at=datetime.fromisoformat(item["created_at"]),
    )


def upsert_user(github_id: str, login: str, name: str | None) -> User:
    """Create or update a profile, preserving the original ``created_at``."""
    existing = get_user(github_id)
    created_at = existing.created_at if existing else datetime.now(UTC)
    item: Item = {
        "PK": user_pk(github_id),
        "SK": _PROFILE_SK,
        "github_id": github_id,
        "login": login,
        "created_at": created_at.isoformat(),
    }
    if name is not None:
        item["name"] = name
    get_table().put_item(Item=item)
    return User(github_id=github_id, login=login, name=name, created_at=created_at)


def store_refresh(
    github_id: str, jti: str, token_hash: str, expires_at: datetime
) -> None:
    get_table().put_item(
        Item={
            "PK": user_pk(github_id),
            "SK": _refresh_sk(jti),
            "github_id": github_id,
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
            "ttl": int(expires_at.timestamp()),
        }
    )


def get_refresh(github_id: str, jti: str) -> Item | None:
    resp = get_table().get_item(Key={"PK": user_pk(github_id), "SK": _refresh_sk(jti)})
    return resp.get("Item")


def consume_refresh(github_id: str, jti: str, token_hash: str) -> bool:
    """Atomically delete a refresh token only when its hash still matches.

    The conditional delete is the single-use boundary: concurrent requests that both
    read a valid token may race here, but exactly one can consume it.
    """
    try:
        get_table().delete_item(
            Key={"PK": user_pk(github_id), "SK": _refresh_sk(jti)},
            ConditionExpression=Attr("token_hash").eq(token_hash),
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def delete_refresh(github_id: str, jti: str) -> None:
    get_table().delete_item(Key={"PK": user_pk(github_id), "SK": _refresh_sk(jti)})
