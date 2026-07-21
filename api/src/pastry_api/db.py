"""DynamoDB access: single-table client + key helpers.

Key schema (see ``spec.md``):

    PK                     SK                 GSI1PK
    USER#<github_id>       PROFILE            —
    USER#<github_id>       PASTE#<ksuid>      SLUG#<slug>
    USER#<github_id>       REFRESH#<jti>      —
    DEVICE#<device_code>   PENDING            —
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3

from pastry_api.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table


@lru_cache
def get_table() -> Table:
    """Return the boto3 Table resource, honoring the dynamodb-local endpoint if set.

    Cached process-wide: constructing a boto3 resource is not free, and a warm Lambda
    reuses this across invocations. Settings are themselves cached (see get_settings).
    """
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
