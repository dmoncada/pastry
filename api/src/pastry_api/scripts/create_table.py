"""Create the single DynamoDB table + GSI1 against dynamodb-local (compose one-shot).

In AWS the table is provisioned by OpenTofu; this script is for local dev only.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from pastry_api.config import get_settings


def create_table() -> None:
    settings = get_settings()
    client = boto3.client(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.ddb_endpoint,
    )

    try:
        client.create_table(
            TableName=settings.table_name,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        print(f"created table {settings.table_name!r}")
        # TODO: dynamodb-local ignores enable_time_to_live; real TTL is set via OpenTofu.
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            print(f"table {settings.table_name!r} already exists")
        else:
            raise


if __name__ == "__main__":
    create_table()
