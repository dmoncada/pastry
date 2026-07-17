"""Shared pytest fixtures: a moto-mocked DynamoDB table + a FastAPI test client.

Dummy AWS creds are set at import time (before any boto3 client is built) so moto can
intercept. The app runs in the default ``auth_mode == "dev"`` (fixed stub user)."""

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from moto import mock_aws  # noqa: E402


@pytest.fixture
def table() -> Iterator[None]:
    """Create the single table (matching create_table.py) inside a moto context."""
    with mock_aws():
        from pastry_api.scripts.create_table import create_table

        create_table()
        yield


@pytest.fixture
def client(table: None) -> TestClient:
    from pastry_api.main import app

    return TestClient(app)
