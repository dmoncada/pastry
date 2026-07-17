"""DynamoDB access: single-table client + key helpers.

Key schema (see ``spec.md``):

    PK                     SK                 GSI1PK
    USER#<github_id>       PROFILE            —
    USER#<github_id>       PASTE#<ksuid>      SLUG#<slug>
    USER#<github_id>       REFRESH#<jti>      —
    DEVICE#<device_code>   PENDING            —
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3

from pastry_api.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table


def get_table() -> Table:
    """Return the boto3 Table resource, honoring the dynamodb-local endpoint if set."""
    settings = get_settings()
    resource = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.ddb_endpoint,
    )
    return resource.Table(settings.table_name)


# --- Key builders -------------------------------------------------------------------


def user_pk(github_id: str) -> str:
    return f"USER#{github_id}"


def paste_sk(ksuid: str) -> str:
    return f"PASTE#{ksuid}"


def slug_gsi1pk(slug: str) -> str:
    return f"SLUG#{slug}"


def refresh_sk(jti: str) -> str:
    return f"REFRESH#{jti}"


def device_pk(device_code: str) -> str:
    return f"DEVICE#{device_code}"


# TODO: item <-> model mapping (to_paste_item / from_paste_item, etc.) lands with slice 1.
